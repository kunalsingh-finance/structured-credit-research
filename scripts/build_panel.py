"""Build the auditable SQLite panel and exact certificate/tape comparison pack.

The panel is disclosure-aware: a source's acceptance_time is retained on every
row. Canonical rows are the first accepted actual monthly filing, not retrospectively
amended observations. Any amended source rows are saved separately. Missing
rows never imply payoff. First-default labels are once per deal/loan; raw monthly
charge-offs and recoveries remain source facts, including repeated charge-offs.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
import gzip
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from credit_research.ingest import (iter_auto_assets, normalize_asset, parse_certificate_html,
    verify_archive, dollar_string)
from credit_research.reconcile import reconcile

TEXT = {"deal_id", "loan_id", "period_start", "period_end", "acceptance_time", "accession", "origination_month",
    "maturity_month", "state", "zero_balance_code", "zero_balance_month", "liquidation_date", "status_code"}
REAL = {"credit_score", "orig_ltv_pct", "interest_rate_pct", "payment_to_income_pct"}
CLOSING_DATES = {"CAOT-2024-2": "2024-04-24", "CAOT-2025-2": "2025-05-02"}


def sources_from_manifests():
    by_url = {}
    for name in ("source_manifest.json", "source_priority_manifest.json"):
        path = ROOT / "data" / name
        if path.exists():
            for source in json.loads(path.read_text())["sources"]:
                by_url.setdefault(source["url"], source)
    return sorted(by_url.values(), key=lambda s: (s.get("deal_id", ""), s.get("report_period", ""), s.get("acceptance_time", "")))


def build_certificates(sources):
    certificates = []
    previous = dict(CLOSING_DATES)
    seen = set()
    for source in sources:
        if source["kind"] != "certificate":
            continue
        key = (source["deal_id"], source["report_period"])
        if key in seen:  # Freeze first accepted certificate; amendments remain in source inventory.
            continue
        with gzip.open(ROOT / source["archive_path"], "rb") as stream:
            certificate = parse_certificate_html(stream.read(), source, previous[source["deal_id"]])
        certificate["certificate_checks"] = reconcile(certificate)
        certificates.append(certificate)
        previous[source["deal_id"]] = certificate["distribution_date"]
        seen.add(key)
    result = {"schema_version": 1, "status": "AUTOMATED_EXTRACTION_FROM_ARCHIVED_SEC_BYTES",
        "original_source_hashes": True, "version_policy": "First accepted actual certificate per deal/month; all versions archived",
        "scope_assumptions": {"finance_charge_repurchases": "0.00", "simple_interest_advances": "0.00",
            "unreimbursed_advances": "0.00", "other_fees": "0.00", "interest_arrears": "0.00",
            "acceleration": False, "cleanup_call": False}, "certificates": certificates}
    (ROOT / "data/actual_certificates.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(certificates)} certificates", flush=True)
    return certificates


def create_tables(connection, columns):
    definitions = [f'"{k}" {"TEXT" if k in TEXT else "REAL" if k in REAL else "INTEGER"}' for k in columns]
    connection.execute("CREATE TABLE IF NOT EXISTS loan_month (" + ",".join(definitions) + ",PRIMARY KEY(deal_id,loan_id,period_end)) WITHOUT ROWID")
    connection.execute("CREATE TABLE IF NOT EXISTS loan_amendment (" + ",".join(definitions) + ",PRIMARY KEY(deal_id,loan_id,period_end,accession)) WITHOUT ROWID")
    connection.execute("CREATE TABLE IF NOT EXISTS ingested_source (accession TEXT PRIMARY KEY, deal_id TEXT, period_end TEXT, acceptance_time TEXT, source_hash TEXT, row_count INTEGER, missing_fields_json TEXT)")
    connection.execute("CREATE INDEX IF NOT EXISTS loan_month_period ON loan_month(deal_id,period_end)")


def derive_events(connection):
    # A loan that reappears after charge-off stays out of the first-default count.
    connection.execute("DROP TABLE IF EXISTS first_default")
    connection.execute("CREATE TEMP TABLE first_default AS SELECT deal_id,loan_id,MIN(period_end) AS first_period FROM loan_month WHERE chargeoff_cents>0 OR instr('|'||coalesce(zero_balance_code,'')||'|','|4|')>0 GROUP BY deal_id,loan_id")
    connection.execute("CREATE UNIQUE INDEX first_default_key ON first_default(deal_id,loan_id)")
    connection.execute("UPDATE loan_month SET first_default_event=0,prepayment_event=0,repurchase_event=0,maturity_event=0,prepayment_cents=NULL")
    connection.execute("UPDATE loan_month SET first_default_event=1 WHERE (deal_id,loan_id,period_end) IN (SELECT deal_id,loan_id,first_period FROM first_default)")
    # SEC code1 combines maturity/payoff. Separate voluntary early payoff using
    # the scheduled maturity month. Multi-code4/3 rows are not voluntary payoffs.
    connection.execute("""UPDATE loan_month SET prepayment_event=1,prepayment_cents=principal_paid_cents
       WHERE instr('|'||coalesce(zero_balance_code,'')||'|','|1|')>0
       AND instr('|'||coalesce(zero_balance_code,'')||'|','|4|')=0
       AND instr('|'||coalesce(zero_balance_code,'')||'|','|3|')=0
       AND end_balance_cents<=0 AND begin_balance_cents>0 AND COALESCE(chargeoff_cents,0)=0
       AND zero_balance_month=substr(period_end,1,7) AND maturity_month>substr(period_end,1,7)
       AND NOT EXISTS (SELECT 1 FROM first_default f WHERE f.deal_id=loan_month.deal_id AND f.loan_id=loan_month.loan_id AND f.first_period<=loan_month.period_end)""")
    connection.execute("""UPDATE loan_month SET maturity_event=1 WHERE instr('|'||coalesce(zero_balance_code,'')||'|','|1|')>0
        AND end_balance_cents<=0 AND begin_balance_cents>0 AND COALESCE(chargeoff_cents,0)=0
        AND instr('|'||coalesce(zero_balance_code,'')||'|','|3|')=0
        AND zero_balance_month=substr(period_end,1,7) AND maturity_month<=substr(period_end,1,7)
        AND NOT EXISTS (SELECT 1 FROM first_default f WHERE f.deal_id=loan_month.deal_id AND f.loan_id=loan_month.loan_id AND f.first_period<=loan_month.period_end)""")
    connection.execute("""UPDATE loan_month SET repurchase_event=1 WHERE instr('|'||coalesce(zero_balance_code,'')||'|','|3|')>0
        AND zero_balance_month=substr(period_end,1,7)""")
    connection.commit()


def panel_comparisons(connection, certificates):
    connection.row_factory = sqlite3.Row
    comparisons = []
    # One sequential scan avoids forty-six secondary-index scans jumping among
    # the same gigabyte of loan-clustered pages. Only 46 grouped rows are kept.
    grouped = connection.execute("""SELECT deal_id,period_end,COUNT(*) row_count, SUM(end_balance_cents>0) positive_balance_count,
          SUM(begin_balance_cents) raw_begin_balance_cents,SUM(end_balance_cents) raw_end_balance_cents,
          SUM(MAX(begin_balance_cents,0)) positive_begin_balance_cents,SUM(MAX(end_balance_cents,0)) positive_end_balance_cents,
          SUM(principal_paid_cents) principal_cents,SUM(interest_paid_cents) interest_cents,
          SUM(COALESCE(chargeoff_cents,0)) raw_chargeoff_cents,SUM(COALESCE(recovery_cents,0)) recovery_cents,
          SUM(COALESCE(other_principal_adjustment_cents,0)) adjustment_cents,
          SUM(first_default_event) first_defaults,SUM(prepayment_event) prepayments,SUM(maturity_event) maturities
          FROM loan_month NOT INDEXED GROUP BY deal_id,period_end""").fetchall()
    periods = {(r["deal_id"], r["period_end"]): dict(r) for r in grouped}
    for cert in certificates:
        statistics = periods.get((cert["deal_id"], cert["collection_period_end"]))
        if not statistics:
            continue
        checks = []
        for name, key, field, explanation in [
            ("outstanding_loan_count", "positive_balance_count", None, "Count strictly positive balances; tapes also retain paid/charged-off rows."),
            ("pool_begin", "positive_begin_balance_cents", "pool_begin", "Sum max(balance,0); small negative credit balances are not outstanding receivables."),
            ("pool_end", "positive_end_balance_cents", "pool_end", "Sum max(balance,0); small negative credit balances are not outstanding receivables."),
            ("principal_collected", "principal_cents", "principal_collected", "Raw loan principal includes non-cash reductions per issuer explanatory exhibit; certificate cash taxonomy differs."),
            ("interest_collected", "interest_cents", "interest_collected", "Raw tape net interest compared with certificate finance-charge collections; unexplained differences remain visible."),
            ("gross_chargeoffs_raw", "raw_chargeoff_cents", "defaults", "Raw chargedoffPrincipalAmount can recur following reinstatement; do not relabel every row a new default."),
            ("recoveries", "recovery_cents", "recoveries", "Recovered amounts are monthly flows, not cumulative; omitted fields remain SQL NULL and sum treats no reported flow as zero."),
        ]:
            reported = cert["outstanding_loan_count"] if field is None else int(Decimal(cert["amounts"][field]) * 100)
            observed = statistics[key]
            residual = observed - reported
            checks.append({"check": name, "observed": observed, "reported": reported, "residual": residual,
                "units": "loans" if field is None else "cents", "status": "PASS" if residual == 0 else "UNRESOLVED_DIFFERENCE", "explanation": explanation})
        comparisons.append({"deal_id": cert["deal_id"], "period_end": cert["collection_period_end"],
            "statistics": statistics, "checks": checks})
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-hashes", action="store_true", help="Read compressed and original bytes to verify full hash chain")
    parser.add_argument("--certificates-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true", help="Rebuild comparisons from committed event labels without changing the panel")
    parser.add_argument("--database", default=str(ROOT / "data/loan_panel.sqlite"))
    args = parser.parse_args()
    sources = sources_from_manifests()
    certificates = build_certificates(sources)
    if args.certificates_only:
        return
    connection = sqlite3.connect(args.database)
    # Loan IDs arrive in servicing-system order rather than B-tree order. The
    # SQLite default 2MB cache otherwise churns hundreds of thousands of pages
    # for every new month. This bounded 256MB cache avoids that I/O bottleneck.
    connection.execute("PRAGMA cache_size=-262144")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    for source in sources:
        if args.summary_only:
            break
        if source["kind"] != "loan_tape":
            continue
        if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ingested_source'").fetchone():
            existing = connection.execute("SELECT source_hash FROM ingested_source WHERE accession=?", (source["accession"],)).fetchone()
            if existing:
                if existing[0] != source["sha256_original_bytes"]:
                    raise ValueError("Previously ingested source hash changed")
                continue
        path = ROOT / source["archive_path"]
        if args.verify_hashes:
            verify_archive(path, source)
        count, columns, insert, batch, missing = 0, None, None, [], Counter()
        with connection:
            for raw in iter_auto_assets(path):
                row = normalize_asset(raw, source)
                if columns is None:
                    columns = list(row)
                    create_tables(connection, columns)
                    table = "loan_amendment" if source.get("is_amendment") else "loan_month"
                    insert = f"INSERT INTO {table} (" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")"
                missing.update(k for k, v in row.items() if v is None)
                batch.append(tuple(row[k] for k in columns))
                count += 1
                if len(batch) == 2000:
                    connection.executemany(insert, batch)
                    batch.clear()
            if not columns:
                raise ValueError("Empty actual loan tape")
            if batch:
                connection.executemany(insert, batch)
            connection.execute("INSERT INTO ingested_source VALUES (?,?,?,?,?,?,?)", (source["accession"], source["deal_id"], source["report_period"],
                source["acceptance_time"], source["sha256_original_bytes"], count, json.dumps(missing)))
        print(f"Ingested {source['deal_id']} {source['report_period']}: {count:,} loan rows", flush=True)
    if not args.summary_only:
        derive_events(connection)
    comparison = panel_comparisons(connection, certificates)
    results = {"schema_version": 1, "database": Path(args.database).name,
        "row_count": connection.execute("SELECT COUNT(*) FROM loan_month").fetchone()[0],
        "source_periods": [dict(r) for r in connection.execute("SELECT deal_id,period_end,acceptance_time,row_count FROM ingested_source ORDER BY deal_id,period_end")],
        "version_policy": "Canonical panel uses first accepted filing; amendments retained separately and not silently substituted.",
        "event_definitions": {"default": "First observed positive chargedoffPrincipalAmount or zeroBalanceCode4 per deal/loan.",
            "prepayment": "Code1 zero-balance before current scheduled maturity; exclude previous default, repurchase and repeat zero-balance rows.",
            "maturity": "Code1 zero-balance at/after current maturity month.",
            "repurchase": "Code3 with zero-balance effective month matching reporting month.",
            "censoring": "End of observation, missed row, transfer/sale or unknown code are not inferred payoffs.",
            "recovery": "Source recoveredAmount is period flow; NULL preserved separately from reported0.",
            "public_availability": "Every row retains actual filing acceptance_time; features must be lagged until accepted."},
        "comparisons": comparison,
        "unresolved_comparisons": sum(c["status"] != "PASS" for p in comparison for c in p["checks"])}
    (ROOT / "data/panel_summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    print(f"Panel ready: {results['row_count']:,} rows; {results['unresolved_comparisons']} visible comparison differences", flush=True)


if __name__ == "__main__":
    main()
