"""Build a bounded historical evidence pack; no downloads or credit predictions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_research.reconcile import parse_amount, reconcile, summarize
from credit_research.waterfall import NOTES, replay


def money(cents: int | None) -> str:
    if cents is None:
        return "Unavailable"
    sign = "−" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}${whole:,}.{fraction:02d}"


def comparison(name: str, computed: int, reported: str) -> dict:
    expected = parse_amount(reported, name)
    residual = computed - expected
    return {"name": name, "computed_cents": computed, "reported_cents": expected,
            "residual_cents": residual, "status": "PASS" if residual == 0 else "DIFFERENCE"}


def compare_replay(certificate: dict, result: dict) -> list[dict]:
    expected = certificate["expected"]
    for group in ("interest", "principal", "note_end"):
        if not isinstance(expected.get(group), dict) or set(expected[group]) != set(NOTES):
            raise ValueError(f"Expected {group} must contain exactly all eight note classes")
    rows = []
    for field in ("servicing_fee", "total_note_interest", "total_note_principal",
                  "residual_distribution", "reserve_deposit", "reserve_end", "reserve_release"):
        rows.append(comparison(field, result[field], certificate["amounts"][field]))
    for group in ("interest", "principal", "note_end"):
        for note, expected in certificate["expected"][group].items():
            rows.append(comparison(f"{group}.{note}", result[group][note], expected))
    for field in ("priority", "secondary", "tertiary", "quaternary", "regular"):
        rows.append(comparison(f"{field}_principal", result[field], certificate["expected"][f"{field}_principal"]))
    rows.append(comparison("oc_target", result["contractual_oc_target"], certificate["expected"]["reported_oc_target"]))
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render(pack: dict) -> str:
    escape = html.escape
    checks = pack["arithmetic_summary"]
    differences = pack["replay_difference_count"]
    oc_differences = sorted({row["residual_cents"] for record in pack["certificates"]
                             for row in record["replay_comparison"] if row["name"] == "oc_target"})
    if any(oc_differences):
        detail = ", ".join(money(value) for value in oc_differences)
        oc_notice = f"Calculated OC target minus reported target: {detail}. The calculation preserves each difference."
    else:
        oc_notice = "The calculated and reported OC targets agree in these samples. Governing-document review remains outstanding."
    cards = []
    for record in pack["certificates"]:
        month = record["collection_period_end"][:7]
        cards.append(f'<article><div class="eyebrow">Collection period {escape(month)}</div>'
                     f'<h2>{escape(record["deal_id"])}</h2><p>Distribution {escape(record["distribution_date"])} · '
                     f'Actual/360 interval {record["replay"]["act_360_days"]} days</p>'
                     f'<p>Observed available collections <strong>{money(record["available_collections_cents"])}</strong></p>'
                     f'<a href="{escape(record["source_url"], quote=True)}">View original certificate</a></article>')
    arithmetic_rows = []
    replay_rows = []
    for record in pack["certificates"]:
        month = record["collection_period_end"][:7]
        for row in record["arithmetic_checks"]:
            arithmetic_rows.append(f'<tr><td>{escape(month)}</td><td>{escape(row["name"])}</td>'
                                   f'<td>{escape(row["status"])}</td><td>{money(row["residual_cents"])}</td></tr>')
        for row in record["replay_comparison"]:
            css = "difference" if row["status"] == "DIFFERENCE" else ""
            replay_rows.append(f'<tr class="{css}"><td>{escape(month)}</td><td>{escape(row["name"])}</td>'
                               f'<td>{money(row["computed_cents"])}</td><td>{money(row["reported_cents"])}</td>'
                               f'<td>{money(row["residual_cents"])}</td></tr>')
    exceptions = "".join(f'<li>{escape(item)}</li>' for item in pack["source_exceptions"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Structured Credit Research — CarMax 2025-2</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f5f1;color:#152b28;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:42px 24px 80px}}h1{{font-size:clamp(30px,5vw,52px);line-height:1.1;margin:16px 0}}h2{{font-size:23px}}a{{color:#176452}}.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:700}}.intro{{max-width:780px;color:#4c615c}}.badge{{display:inline-block;padding:8px 12px;border-radius:4px;background:#fbdf9c;color:#654612;font-weight:700}}.metrics,.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin:28px 0}}.metric,article{{background:white;border:1px solid #d6dfd9;padding:22px;border-radius:8px}}.metric strong{{display:block;font-size:32px}}.metric span{{color:#526560;font-size:14px}}section{{margin-top:40px}}.notice{{border-left:4px solid #b6872b;background:#fff7e5;padding:18px 22px}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:white;font-size:14px}}th,td{{padding:11px 13px;border-bottom:1px solid #e4e8e3;text-align:left}}th{{background:#153c33;color:white}}td:nth-last-child(-n+3){{font-variant-numeric:tabular-nums}}tr.difference{{background:#fff1d3}}.small{{font-size:13px;color:#586b65}}footer{{margin-top:48px;border-top:1px solid #cfdad3;padding-top:20px}}code{{word-break:break-all}}
</style></head><body><main><div class="eyebrow">Independent portfolio research · Development evidence</div>
<h1>Structured Credit<br>Research Platform</h1><p class="intro">Reconstruct the cash flows of a real auto-loan securitization, then connect borrower performance to bond risk. First case: CarMax Auto Owner Trust 2025-2.</p>
<span class="badge">{escape(pack["status"])}</span><div class="metrics"><div class="metric"><strong>{checks['PASS']}/{checks['total']}</strong><span>Reported-data arithmetic checks pass</span></div><div class="metric"><strong>{differences}</strong><span>Calculated-versus-reported replay differences</span></div><div class="metric"><strong>{len(pack['certificates'])}</strong><span>Actual development samples</span></div></div>
<div class="notice"><strong>The OC rule requires document review.</strong> {escape(oc_notice)} Arithmetic consistency does not establish that the governing contract has been fully reproduced.</div>
<div class="cards">{''.join(cards)}</div><section><h2>What has been built</h2><p>Exact-cent pool, cash, note and reserve reconciliations; a bounded pre-acceleration cash-flow replay; source-row mappings; and calculated-versus-reported comparisons. Floating coupons use observed certificate rates. The replay uses observed collateral cash and end-of-period collateral balances.</p><p class="small">Fully funded ordinary distributions before final maturities only. Acceleration, arrears, unusual fees, reserve draws and cleanup calls are outside this replay. Unsupported cases are rejected.</p></section>
<section><h2>Reported-data consistency</h2><div class="table-wrap"><table><thead><tr><th>Period</th><th>Identity</th><th>Status</th><th>Computed − reported</th></tr></thead><tbody>{''.join(arithmetic_rows)}</tbody></table></div></section>
<section><h2>Prospectus-based replay</h2><p class="small">These are development comparisons. They are neither withheld-month mechanical validation nor forecast backtesting.</p><div class="table-wrap"><table><thead><tr><th>Period</th><th>Calculated quantity</th><th>Calculated</th><th>Reported</th><th>Difference</th></tr></thead><tbody>{''.join(replay_rows)}</tbody></table></div></section>
<section><h2>Source exceptions</h2><ul>{exceptions}</ul></section>
<section><h2>Build toward a credit decision</h2><ol><li>Archive original filings, ingest consecutive certificates, and review executed terms and amendments.</li><li>Validate contractual cash flows on subsequent months withheld from development.</li><li>Reconcile post-close loan tapes and build a point-in-time credit panel.</li><li>Estimate and test default, prepayment and recovery behaviour against transparent baselines.</li><li>Stress bond cash flows, loss exposure and principal timing, then write a supported credit memo.</li></ol></section>
<footer><p><a href="../README.md">Project scope</a> · <a href="../docs/RESEARCH_DESIGN.md">Method and release gates</a> · <a href="research_results.json">Machine-readable evidence</a> · <a href="replay_comparison.csv">Replay comparison CSV</a></p><p class="small">Manual numeric extraction from SEC HTML; original source bytes and source hashes unavailable. Local fixture SHA-256: <code>{pack['normalized_fixture_sha256']}</code>. No loan-level model, market quote, investment conclusion or predictive holdout exists yet.</p><p class="small">Generated {escape(pack['generated_at'])}</p></footer></main></body></html>'''


ZERO_ASSUMPTIONS = ("finance_charge_repurchases", "simple_interest_advances", "unreimbursed_advances", "other_fees", "interest_arrears")
FALSE_ASSUMPTIONS = ("acceleration", "cleanup_call")


def validate_scope(assumptions: dict) -> None:
    if not isinstance(assumptions, dict) or set(assumptions) != set(ZERO_ASSUMPTIONS + FALSE_ASSUMPTIONS):
        raise ValueError("All supported-scope assumptions must be explicitly supplied")
    for name in ZERO_ASSUMPTIONS:
        if parse_amount(assumptions[name], name) != 0:
            raise ValueError(f"Nonzero {name} is outside this research replay")
    for name in FALSE_ASSUMPTIONS:
        if assumptions[name] is not False:
            raise ValueError(f"{name} must be explicitly false for this research replay")


def validate_note_evidence(certificate: dict) -> None:
    inputs = certificate["replay_inputs"]
    expected = certificate["expected"]
    aggregate_fields = {"interest": "total_note_interest", "principal": "total_note_principal", "note_end": "note_end"}
    for group, aggregate in aggregate_fields.items():
        if not isinstance(expected.get(group), dict) or set(expected[group]) != set(NOTES):
            raise ValueError(f"Expected {group} must contain exactly all eight note classes")
        if sum(parse_amount(value, f"expected.{group}") for value in expected[group].values()) != parse_amount(certificate["amounts"][aggregate]):
            raise ValueError(f"Expected {group} does not reconcile with the reported aggregate")
    beginning = inputs.get("note_begin")
    if not isinstance(beginning, dict) or set(beginning) != set(NOTES):
        raise ValueError("Replay note_begin must contain exactly all eight note classes")
    if sum(parse_amount(value, "note_begin") for value in beginning.values()) != parse_amount(certificate["amounts"]["note_begin"]):
        raise ValueError("Replay beginning note balances do not reconcile with certificate aggregate")


def build(fixture: dict) -> dict:
    if type(fixture.get("schema_version")) is not int or fixture["schema_version"] != 1 or not isinstance(fixture.get("certificates"), list) or not fixture["certificates"]:
        raise ValueError("Expected schema_version1 with at least one certificate")
    validate_scope(fixture.get("scope_assumptions"))
    records = []
    all_checks = []
    exceptions = set()
    keys = set()
    for certificate in fixture["certificates"]:
        key = (certificate["deal_id"], certificate["collection_period_end"])
        if certificate["deal_id"] != "CAOT-2025-2":
            raise ValueError("Replay terms support only CarMax Auto Owner Trust2025-2")
        if key in keys:
            raise ValueError("Duplicate deal and collection period")
        keys.add(key)
        rows = reconcile(certificate)
        collection = datetime.fromisoformat(certificate["collection_period_end"])
        distribution = datetime.fromisoformat(certificate["distribution_date"])
        if distribution.year * 12 + distribution.month != collection.year * 12 + collection.month + 1:
            raise ValueError("This deal's distribution must occur in the month following collection")
        if "scope_assumptions" in certificate:
            validate_scope(certificate["scope_assumptions"])
        validate_note_evidence(certificate)
        inputs = dict(certificate["replay_inputs"])
        for name in ("pool_begin", "pool_end", "available_collections", "reserve_begin", "reserve_interest"):
            if inputs[name] != certificate["amounts"][name]:
                raise ValueError(f"Replay and certificate inputs disagree on {name}")
        if inputs["distribution_date"] != certificate["distribution_date"]:
            raise ValueError("Replay distribution date differs from certificate")
        for name in ("reserve_draw", "trustee_fee"):
            if parse_amount(certificate["amounts"][name], name) != 0:
                raise ValueError(f"Nonzero certificate {name} is outside this research replay")
        assumptions = fixture["scope_assumptions"]
        canonical_conditions = dict(accelerated=assumptions["acceleration"], cleanup_call=assumptions["cleanup_call"],
                                    interest_arrears=assumptions["interest_arrears"], additional_fees=assumptions["other_fees"],
                                    unreimbursed_servicer_advances=assumptions["unreimbursed_advances"],
                                    reserve_draw=certificate["amounts"]["reserve_draw"])
        for name, canonical in canonical_conditions.items():
            if name in inputs:
                matches = inputs[name] is canonical if isinstance(canonical, bool) else parse_amount(inputs[name], name) == parse_amount(canonical, name)
                if not matches:
                    raise ValueError(f"Replay condition {name} contradicts the documented certificate scope")
        inputs.update(canonical_conditions)
        result = replay(inputs)
        comparison_rows = compare_replay(certificate, result)
        records.append({"deal_id": certificate["deal_id"], "collection_period_end": certificate["collection_period_end"],
                        "distribution_date": certificate["distribution_date"], "accession": certificate["accession"],
                        "source_url": certificate["source_url"], "extraction_method": certificate["extraction_method"],
                        "available_collections_cents": parse_amount(certificate["amounts"]["available_collections"]),
                        "arithmetic_checks": rows, "replay": result, "replay_comparison": comparison_rows})
        all_checks.extend(rows)
        exceptions.update(certificate.get("source_exceptions", []))
    summary = summarize(all_checks)
    difference_count = sum(row["status"] == "DIFFERENCE" for record in records for row in record["replay_comparison"])
    status = "REVIEW REQUIRED" if difference_count or exceptions else "DEVELOPMENT ONLY"
    if summary["status"] != "PASS":
        status = "ARITHMETIC CHECKS " + summary["status"]
    return {"status": status, "generated_at": datetime.now(timezone.utc).isoformat(),
            "arithmetic_summary": summary, "replay_difference_count": difference_count,
            "certificates": records, "source_exceptions": sorted(exceptions),
            "original_source_hashes": None, "normalized_fixture_sha256": None,
            "evidence_type": "Manually extracted development samples; observed-cash replay; not a forecast or a holdout."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-exact-replay", action="store_true", help="Exit2 if arithmetic or replay differences remain")
    parser.add_argument("--output-dir", default=str(ROOT / "output"), help="Destination for the original bounded fixture pack")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(exist_ok=True, parents=True)
    report_path = output / "research_report.html"
    report_path.write_text("<!doctype html><html><title>Research rebuilding</title><body><h1>Evidence pack rebuilding</h1><p>No current result is available.</p></body></html>", encoding="utf-8")
    (output / "run_status.json").write_text(json.dumps({"status": "BUILDING"}), encoding="utf-8")
    (output / "research_results.json").write_text(json.dumps({"status": "BUILDING", "certificates": []}), encoding="utf-8")
    write_csv(output / "reconciliation_checks.csv", [], ["collection_period", "check_id", "name", "status", "computed_cents", "reported_cents", "residual_cents", "formula"])
    write_csv(output / "replay_comparison.csv", [], ["collection_period", "name", "status", "computed_cents", "reported_cents", "residual_cents"])
    try:
        fixture_path = ROOT / "data" / "certificates.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        pack = build(fixture)
        pack["normalized_fixture_sha256"] = sha256(fixture_path)
        pack["source_manifest_sha256"] = sha256(ROOT / "configs" / "source_manifest.json")
        pack["code_sha256"] = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
                              for path in sorted((ROOT / "credit_research").glob("*.py"))}
        pack["code_sha256"]["scripts/run_research.py"] = sha256(Path(__file__).resolve())
        arithmetic = [{"collection_period": record["collection_period_end"], **row}
                      for record in pack["certificates"] for row in record["arithmetic_checks"]]
        replay_rows = [{"collection_period": record["collection_period_end"], **row}
                       for record in pack["certificates"] for row in record["replay_comparison"]]
        write_csv(output / "reconciliation_checks.csv", arithmetic, ["collection_period", "check_id", "name", "status", "computed_cents", "reported_cents", "residual_cents", "formula"])
        write_csv(output / "replay_comparison.csv", replay_rows, ["collection_period", "name", "status", "computed_cents", "reported_cents", "residual_cents"])
        (output / "research_results.json").write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
        report_path.write_text(render(pack), encoding="utf-8")
        (output / "run_status.json").write_text(json.dumps({"status": pack["status"], "generated_at": pack["generated_at"], "original_sources_archived": False}, indent=2) + "\n", encoding="utf-8")
        print(f"{pack['status']}: {pack['arithmetic_summary']['PASS']}/{pack['arithmetic_summary']['total']} arithmetic checks pass; {pack['replay_difference_count']} replay differences.")
        print(f"Report: {report_path}")
        if args.require_exact_replay and (pack["replay_difference_count"] or pack["arithmetic_summary"]["status"] != "PASS"):
            return 2
        return 0
    except Exception as error:
        message = f"{type(error).__name__}: {error}"
        (output / "run_status.json").write_text(json.dumps({"status": "ERROR", "message": message}, indent=2) + "\n", encoding="utf-8")
        (output / "research_results.json").write_text(json.dumps({"status": "ERROR", "message": message, "certificates": []}, indent=2) + "\n", encoding="utf-8")
        write_csv(output / "reconciliation_checks.csv", [], ["collection_period", "check_id", "name", "status", "computed_cents", "reported_cents", "residual_cents", "formula"])
        write_csv(output / "replay_comparison.csv", [], ["collection_period", "name", "status", "computed_cents", "reported_cents", "residual_cents"])
        report_path.write_text(f"<!doctype html><html><title>Research error</title><body><h1>Evidence pack unavailable</h1><p>{html.escape(message)}</p></body></html>", encoding="utf-8")
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
