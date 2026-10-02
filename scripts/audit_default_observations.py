"""Read-only audit of first observed defaults, effective dates and reinstatements.

First observed is a disclosure label. It is not a claim that the legal default
occurred during that reporting month, especially at the first tape boundary.
The SQLite panel is opened mode=ro and is never updated by this script.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def main():
    database = ROOT / "data/loan_panel.sqlite"
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA cache_size=-262144")
    rows = connection.execute("""SELECT deal_id,loan_id,period_end,
        begin_balance_cents,end_balance_cents,chargeoff_cents,
        zero_balance_code,zero_balance_month,first_default_event,
        principal_paid_cents,other_principal_adjustment_cents
        FROM loan_month ORDER BY deal_id,loan_id,period_end""")
    counters = Counter({"positive_end_first_default_rows": 0,
                        "positive_end_chargedoff_code_rows": 0,
                        "balance_identity_failures": 0,
                        "balance_identity_residual_cents": 0})
    by_period = {}
    prior_key = None
    first_default_seen = False
    prior_end = None
    reinstatement_loans = set()
    first_periods = dict(connection.execute(
        "SELECT deal_id,MIN(period_end) FROM ingested_source GROUP BY deal_id"))
    for deal, loan, period, begin, end, chargeoff, codes, effective, event, principal, adjustment in rows:
        key = (deal, loan)
        if key != prior_key:
            first_default_seen = False
            prior_end = None
            prior_key = key
        counters["rows"] += 1
        record = by_period.setdefault((deal, period), Counter())
        record["rows"] += 1
        assert begin is not None and end is not None and principal is not None
        residual = begin - end - principal - (chargeoff or 0) - (adjustment or 0)
        counters["balance_identity_failures"] += int(residual != 0)
        counters["balance_identity_residual_cents"] += residual
        record["balance_identity_failures"] += int(residual != 0)
        record["balance_identity_residual_cents"] += residual
        record["net_chargeoff_adjustments"] += (chargeoff or 0) + (adjustment or 0)
        if effective == period[:7]:
            record["effective_month_chargeoffs"] += chargeoff or 0
        if event:
            counters["first_observed_defaults"] += 1
            record["first_observed_defaults"] += 1
            record["first_default_chargeoffs"] += chargeoff or 0
            record["first_default_begin_balance"] += begin
            category = ("missing" if effective is None else
                        "earlier" if effective < period[:7] else
                        "same" if effective == period[:7] else "later")
            counters[f"first_default_effective_month_{category}"] += 1
            record[f"first_default_effective_month_{category}"] += 1
            if period == first_periods[deal]:
                counters["first_tape_boundary_default_rows"] += 1
                record["first_tape_boundary_default_rows"] += 1
            if end > 0:
                counters["positive_end_first_default_rows"] += 1
                record["positive_end_first_default_rows"] += 1
        if end > 0 and "4" in (codes or "").split("|"):
            counters["positive_end_chargedoff_code_rows"] += 1
            record["positive_end_chargedoff_code_rows"] += 1
        if first_default_seen and end > 0:
            counters["positive_end_after_observed_default_rows"] += 1
            record["positive_end_after_observed_default_rows"] += 1
            reinstatement_loans.add(key)
            if prior_end is not None and prior_end <= 0:
                counters["nonpositive_to_positive_after_default_transitions"] += 1
                record["nonpositive_to_positive_after_default_transitions"] += 1
        if first_default_seen and (chargeoff or 0) > 0:
            counters["positive_chargeoff_rows_after_first_observed_default"] += 1
            record["positive_chargeoff_rows_after_first_observed_default"] += 1
        first_default_seen = first_default_seen or bool(event)
        prior_end = end
    connection.close()
    result = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": "loan_panel.sqlite",
        "status": "READ_ONLY_DISCLOSURE_EVENT_AUDIT",
        "interpretation": "first observed default differs from issuer effective month; repeated chargeoff flows are not new first defaults",
        "counts": dict(counters),
        "unique_positive_balance_loans_after_observed_default": len(reinstatement_loans),
        "periods": [{"deal_id": d, "period_end": p, **dict(c)}
                    for (d, p), c in sorted(by_period.items())],
    }
    (ROOT / "data/default_observation_audit.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    diagnostic_fields = ("first_default_chargeoffs", "first_default_begin_balance",
                         "effective_month_chargeoffs", "net_chargeoff_adjustments", "rows",
                         "balance_identity_failures", "balance_identity_residual_cents",
                         "positive_end_first_default_rows", "positive_end_chargedoff_code_rows")
    diagnostics = [{"deal_id": deal, "period_end": period,
                    "first_defaults": record["first_observed_defaults"],
                    **{name: record[name] for name in diagnostic_fields}}
                   for (deal, period), record in sorted(by_period.items())]
    (ROOT / "data/source_bridge_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2), flush=True)
    print("Unique reinstatement loans:", len(reinstatement_loans), flush=True)


if __name__ == "__main__":
    main()
