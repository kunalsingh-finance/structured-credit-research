"""Reproduce the full research release from the archived, reconciled source panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_research.cashflows import (CollateralPeriod, DealTerms, ScenarioState, distribute_period, run_scenario, reverse_stress)
from credit_research.credit_models import load_panel, train_credit_models
from credit_research.cash_validation import evaluate_cash_forecasts
from credit_research.projections import make_cohorts, project_collateral
from credit_research.reconcile import parse_amount, reconcile, summarize
from credit_research.waterfall import NOTES, INITIAL_POOL_CENTS
from scripts.run_research import compare_replay


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def source_provenance():
    sources = {}
    for name in ("source_manifest.json", "source_priority_manifest.json"):
        path = ROOT / "data" / name
        if path.exists():
            for s in read(path)["sources"]:
                sources.setdefault(s["url"], s)
    return [{"title": f"{s.get('deal_id', 'SEC')} {s['kind']} {s.get('report_period', '')}",
             "url": s["url"], "path": s["archive_path"], "sha256": s["sha256_original_bytes"],
             "archive_sha256": s["sha256_archive"], "bytes": s["original_byte_count"],
             "role": s["kind"], "period": s.get("report_period"), "accepted": s.get("acceptance_time"),
             "accession": s.get("accession")} for s in sources.values()]


def historical_replay(certificates):
    records, checks, exceptions = [], [], []
    for c in certificates:
        arithmetic = [v.as_dict() if hasattr(v, "as_dict") else v for v in reconcile(c)]
        checks.extend(arithmetic)
        exceptions.extend(c.get("source_exceptions", []))
        if c["deal_id"] != "CAOT-2025-2" or c["replay_inputs"]["prior_distribution_date"] < "2025-05-15":
            continue  # The issuance stub and 2024 deal have different legal terms.
        a = c["amounts"]
        i = c["replay_inputs"]
        state = ScenarioState(parse_amount(a["pool_begin"]), {n: parse_amount(i["note_begin"][n]) for n in NOTES},
                              parse_amount(a["reserve_begin"]), i["prior_distribution_date"])
        period = CollateralPeriod(c["distribution_date"], parse_amount(a["pool_end"]),
                                  parse_amount(a["principal_collected"]), parse_amount(a["interest_collected"]),
                                  recoveries=parse_amount(a["recoveries"]), defaults=parse_amount(a["defaults"]),
                                  repurchases=parse_amount(a["repurchases"]), investment_income=parse_amount(a["investment_income"]),
                                  reserve_interest=parse_amount(a["reserve_interest"]), floating_note_rate=i["floating_note_rate"],
                                  trustee_fee=parse_amount(a["trustee_fee"]))
        _, r = distribute_period(state, period)
        adapter = dict(r)
        adapter.update(contractual_oc_target=r["oc_target"], servicing_fee=r["servicing_paid"], total_note_interest=sum(r["interest"].values()),
                       total_note_principal=sum(r["principal"].values()), **r["principal_tier_due"])
        comparisons = compare_replay(c, adapter)
        records.append({"deal_id": c["deal_id"], "collection_period_end": c["collection_period_end"],
                        "distribution_date": c["distribution_date"], "source_url": c["source_url"],
                        "source_sha256": c["source_sha256"], "arithmetic_checks": arithmetic,
                        "replay_comparison": comparisons, "holdout": c["collection_period_end"] >= "2026-02-01",
                        "replay": r})
    differences = sum(v["status"] != "PASS" for c in records for v in c["replay_comparison"])
    return records, summarize(checks), differences, sorted(set(exceptions))


def build_scenario(name, description, cohorts, state, assumptions, unmapped_cents=0):
    periods, pool_rows = project_collateral(cohorts, state.prior_distribution_date,
                                          annual_default_rate=assumptions["annual_default_rate"],
                                          annual_prepayment_rate=assumptions["annual_prepayment_rate"],
                                          recovery_rate=assumptions["recovery_rate"],
                                          recovery_lag_months=assumptions["recovery_lag_months"],
                                          interest_collection_factor=assumptions["interest_collection_factor"],
                                          floating_note_rate=assumptions["floating_note_rate"])
    if unmapped_cents:
        # Explicit adverse bound: the source-to-source collateral difference is
        # a separate unreconciled amount, immediately written off without any
        # assumed collection/recovery. It is never made into a fabricated loan.
        periods[0]["defaults"] += unmapped_cents
        pool_rows[0]["pool_begin_cents"] += unmapped_cents
        pool_rows[0]["default_cents"] += unmapped_cents
        pool_rows[0]["net_loss_cents"] += unmapped_cents
        pool_rows[0]["source_exception_loss_cents"] = unmapped_cents
    result = run_scenario(state, [CollateralPeriod(**p) for p in periods], terminal=True)
    if not result["checks"]["horizon_closed"]:
        raise ValueError(f"{name}: modeled collateral and recoveries did not close")
    origin = date.fromisoformat(state.prior_distribution_date)
    for t in result["tranches"]:
        n = t["name"]
        idx = NOTES.index(n)
        subordinate = sum(state.note_balances[x] for x in NOTES[idx + 1:])
        # A2a and A2b share a rank; neither provides subordination to the other.
        if n in ("A2a", "A2b"):
            subordinate = sum(state.note_balances[x] for x in ("A3", "A4", "B", "C", "D"))
        t["credit_enhancement_pct"] = ((subordinate + state.pool_balance - sum(state.note_balances.values()) + state.reserve_balance) / state.pool_balance) if t["opening_balance_cents"] else None
        t["coupon"] = float(assumptions["floating_note_rate"] if n == "A2b" else DealTerms().fixed_rates[n])
        pv = 0.0
        for month, row in enumerate(t["rows"], 1):
            row["month"] = month
            row["time_years"] = (date.fromisoformat(row["distribution_date"]) - origin).days / 365.25
            row["contractual_closing_balance_cents"] = row["closing_balance_cents"]
            row["closing_balance_cents"] = row.get("economic_closing_balance_cents", row["closing_balance_cents"])
            row["interest_arrears_cents"] = row["interest_shortfall_cents"]
            pv += (row["principal_paid_cents"] + row["interest_paid_cents"]) / (1 + assumptions["discount_rate"]) ** row["time_years"]
        t["model_price_per_100"] = pv / t["opening_balance_cents"] * 100 if t["opening_balance_cents"] else None
    return {"name": name, "description": description, "assumptions": assumptions, "pool_rows": pool_rows,
            "tranches": result["tranches"], "checks": result["checks"], "monthly": result["monthly"],
            "limits": result["limits"], "legal_sources": result["legal_sources"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=str(ROOT / "data/loan_panel.sqlite"))
    parser.add_argument("--credit-cache", action="store_true", help="Reuse matching panel/protocol credit results while rebuilding scenarios")
    parser.add_argument("--require-exact-reconciliation", action="store_true", help="Exit2 unless all full-corpus tape/certificate and contractual replay comparisons agree")
    parser.add_argument("--include-supplements", action="store_true", help="Include separately completed, identity-checked model and legal/rate review studies")
    args = parser.parse_args()
    summary = read(ROOT / "data/panel_summary.json")
    actual = read(ROOT / "data/actual_certificates.json")["certificates"]
    if len(summary["source_periods"]) != len(actual) or len(actual) != 46:
        raise ValueError("Complete46-period actual certificate/tape corpus is required")
    panel = load_panel(args.panel)
    (ROOT / "output").mkdir(exist_ok=True)
    protocol_hash = hashlib.sha256((ROOT / "configs/research_protocol.json").read_bytes()).hexdigest()
    identity = {"panel_rows": len(panel), "panel_sha256": hash_file(args.panel),
                "source_fingerprint": hashlib.sha256(json.dumps(summary["source_periods"], sort_keys=True).encode()).hexdigest(),
                "protocol_sha256": protocol_hash,
                "model_code_sha256": hash_file(ROOT / "credit_research/credit_models.py"),
                "cash_validation_code_sha256": hash_file(ROOT / "credit_research/cash_validation.py"),
                "projection_code_sha256": hash_file(ROOT / "credit_research/projections.py"),
                "certificate_sha256": hash_file(ROOT / "data/actual_certificates.json")}
    release_paths = list((ROOT / "credit_research").glob("*.py")) + [ROOT / "scripts/run_platform.py", ROOT / "scripts/run_research.py"]
    release_code = {path.relative_to(ROOT).as_posix(): hash_file(path) for path in release_paths}
    cache = ROOT / "output/credit_model_results.json"
    if args.credit_cache and cache.exists() and read(cache).get("build_identity") == identity and "cashflow_validation" in read(cache):
        model = read(cache)
    else:
        print(f"Fitting frozen-protocol credit model on {len(panel):,} actual loan months", flush=True)
        model, predict = train_credit_models(panel)
        print("Scoring disclosure-origin cash forecasts against future reported servicing cash", flush=True)
        model["cashflow_validation"] = evaluate_cash_forecasts(panel, actual, predict, model["baseline_probabilities"])
        model["build_identity"] = identity
        cache.write_text(json.dumps(model, indent=2, allow_nan=False), encoding="utf-8")
    records, arithmetic, replay_differences, source_exceptions = historical_replay(actual)
    latest = max((c for c in actual if c["deal_id"] == "CAOT-2025-2"), key=lambda c: c["collection_period_end"])
    target = panel[panel.deal_id == "CAOT-2025-2"]
    active = target[(target.period_end == target.period_end.max()) & (target.end_balance_cents > 0)].copy()
    defaulted = set(target.loc[target.first_default_event == 1, "loan_id"])
    active["previously_defaulted"] = active.loan_id.isin(defaulted)
    mapped_pool = int(active.end_balance_cents.sum())
    certificate_pool = parse_amount(latest["amounts"]["pool_end"])
    residual = certificate_pool - mapped_pool
    if residual < 0 or residual / certificate_pool > .00001:
        raise ValueError("Collateral mismatch cannot be bounded by the documented positive small-residual convention")
    cohorts, cohort_info = make_cohorts(active, mapped_pool)
    state = ScenarioState(certificate_pool, {n: parse_amount(latest["expected"]["note_end"][n]) for n in NOTES},
                          parse_amount(latest["amounts"]["reserve_end"]), latest["distribution_date"])
    forecast = model["forecast"]
    recovery = model["recovery_cohorts"]
    recovery_rate = recovery.get("observed_recovery_fraction", forecast["observed_recovery_flow_ratio"])
    if not 0 <= recovery_rate <= 1:
        raise ValueError("Observed recovery benchmark cannot be interpreted as a recovery fraction")
    lag = max(1, recovery.get("median_recovery_flow_lag_months", 3))
    # Calibrate aggregate contractual APR cash collection on the latest observed
    # certificate, retaining this factor as an explicit assumption in stresses.
    latest_rows = target[target.period_end == target.period_end.max()]
    source_apr = latest_rows.interest_rate_pct.fillna(latest_rows.interest_rate_pct.dropna().median()) / 100
    contractual_interest = float((latest_rows.begin_balance_cents.clip(lower=0) * source_apr / 12).sum())
    collection_ratio = parse_amount(latest["amounts"]["interest_collected"]) / contractual_interest
    factor = min(1.0, collection_ratio)
    cohort_info["interest_collection_proxy"] = {"observed_cents": parse_amount(latest["amounts"]["interest_collected"]),
                "beginning_balance_apr_proxy_cents": contractual_interest, "uncapped_ratio": collection_ratio,
                "collection_factor": factor, "capped_at_one": collection_ratio > 1,
                "method": "Latest reported finance-charge cash divided by beginning-balance APR/12 proxy; an economic collection assumption, not exact cash calibration"}
    central = dict(annual_default_rate=forecast["annual_default_rate"], annual_prepayment_rate=forecast["annual_prepayment_rate"],
                   recovery_rate=recovery_rate, recovery_lag_months=lag, interest_collection_factor=factor,
                   floating_note_rate=latest["replay_inputs"]["floating_note_rate"], discount_rate=.08)
    def assumptions(default_multiple=1, prepay_multiple=1, recovery_multiple=1, extra_lag=0, interest_multiple=1):
        a = dict(central)
        a.update(annual_default_rate=1 - (1 - central["annual_default_rate"]) ** default_multiple,
                 annual_prepayment_rate=1 - (1 - central["annual_prepayment_rate"]) ** prepay_multiple,
                 recovery_rate=central["recovery_rate"] * recovery_multiple,
                 recovery_lag_months=central["recovery_lag_months"] + extra_lag,
                 interest_collection_factor=central["interest_collection_factor"] * interest_multiple)
        return a
    scenarios = [
        build_scenario("Central", "Calibrated first-event hazards, seasoned twelve-month recovery benchmark, disclosed contractual term cohorts", cohorts, state, assumptions(), residual),
        build_scenario("Downside", "Two-times default hazard, slower prepayments, lower and delayed recoveries, lower interest collections", cohorts, state, assumptions(2, .75, .75, 3, .95), residual),
        build_scenario("Severe", "Five-times default hazard, half prepayment hazard, half recovery fraction and extended recovery delay", cohorts, state, assumptions(5, .5, .5, 6, .85), residual)]
    def factory(s):
        return build_scenario("Reverse", "Joint shock grid", cohorts, state, assumptions(float(s), .5, .5, 6, .85), residual)
    reverse = reverse_stress(factory, [str(x) for x in (1, 2, 3, 5, 7, 10, 15, 20, 30)], tranche="D")
    forecast_metrics = []
    for split, evaluation in model["evaluations"].items():
        for event in ("default", "prepayment"):
            for metric in ("brier", "auc", "balance_mae_cents"):
                baseline = evaluation["constant_baseline"]["events"][event][metric]
                fitted = evaluation["calibrated_multinomial"]["events"][event][metric]
                forecast_metrics.append({"metric": f"{split}: {event} {metric}", "baseline_mae": baseline,
                                         "model_mae": fitted, "unit": "cents of first-event beginning exposure" if metric == "balance_mae_cents" else "score"})
    principal_loss = [sum(t["loss_cents"] for t in s["tranches"]) for s in scenarios]
    model["target_definition"] = "First-observed default disclosure, voluntary prepayment, or survival in the conditional eligible risk set"
    disclosure_limit = "Default labels and recovery cohort ages start at first public observation, which can follow the reported effective default month. Mapping disclosure hazards into economic principal defaults is a scenario assumption; cash backtesting exposes the combined timing and projection error."
    if disclosure_limit not in model["limitations"]:
        model["limitations"].append(disclosure_limit)
    limits = model["limitations"] + [
        f"Latest tape mapped principal is ${mapped_pool / 100:,.2f}; certificate reports ${certificate_pool / 100:,.2f}. The unexplained ${residual / 100:,.2f} is a separate unreconciled amount assigned immediate full loss in every scenario, with no assumed recovery.",
        "The executed 0.75% cutoff overcollateralization rule differs from reported targets by $76.08. Mechanical comparisons retain this exception rather than replacing terms with expected outputs.",
        "Forecasts begin at the August 2026 reported collateral snapshot, including the unreported bridge interval. They are not observed September/October performance.",
        "Discount rate 8% and floating coupon held at the latest reported rate are research assumptions, not executable quotes or a predicted SOFR path.",
        "Acceleration and optional purchase election remain explicit scenario choices. Ordinary runoff scenarios do not infer legal notices, issuer elections or default remedies.",
        "Any terminal unpaid principal is economic impairment after modeled recoveries exhaust, not a cash payment or an official legal writeoff."
    ]
    limits.append("Cash holdouts are mixed: model default and interest MAE improve over the pooled baseline, while principal-collection and ending-pool MAE worsen in both deals. Scenario runoff is illustrative and has not established reliable investment forecasting.")
    gates = {
        "consecutive_real_data": {"status": "PASS", "periods": len(actual)},
        "certificate_internal_accounting": {"status": arithmetic["status"], "checks": arithmetic["total"]},
        "tape_to_certificate": {"status": "FAIL" if summary["unresolved_comparisons"] else "PASS", "unresolved": summary["unresolved_comparisons"]},
        "exact_contractual_replay": {"status": "FAIL" if replay_differences else "PASS", "differences": replay_differences, "periods": len(records)},
        "credit_model": {"status": "PARTIAL", "evidence": "Chronological and unseen-deal holdouts, calibration, transition baselines and conditional cluster intervals; expanding-window and segment-stability analysis remain open"},
        "cash_forecast": {"status": "MIXED", "evidence": "Seven target months per deal; default and interest improve while principal and ending-pool errors worsen"},
        "scenario_conservation": {"status": "PASS"},
        "valuation": {"status": "ASSUMPTION_ONLY", "evidence": "September15,2026 origin; common8% annual discount rate; no executable market quote"}}
    pack = {
        "schema_version": 2, "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DEVELOPMENT RESEARCH WITH UNRESOLVED SOURCE EXCEPTIONS", "build_identity": identity, "release_code_sha256": release_code,
        "platform": {"deal_name": "CarMax Auto Owner Trust 2025-2", "deal_id": "CAOT-2025-2",
                     "as_of": latest["collection_period_end"], "source_acceptance_time": latest["acceptance_time"],
                     "valuation_date": latest["distribution_date"],
                     "initial_pool_cents": INITIAL_POOL_CENTS, "latest_pool_cents": certificate_pool,
                     "mapped_pool_cents": mapped_pool, "unmapped_collateral_cents": residual,
                     "loan_count": int(panel[["deal_id", "loan_id"]].drop_duplicates().shape[0]),
                     "active_target_loans": len(active), "loan_months": len(panel), "actual_periods": len(actual),
                     "train_periods": model["training_periods"], "holdout_periods": model["holdout_periods"],
                     "projection_origin": state.prior_distribution_date, "cohort_method": cohort_info},
        "certificates": records, "arithmetic_summary": arithmetic, "replay_difference_count": replay_differences,
        "source_exceptions": source_exceptions, "loan_tape_reconciliation": summary,
        "research_gates": gates,
        "source_verification": read(ROOT / "data/source_verification.json"),
        "default_observation_audit": read(ROOT / "data/default_observation_audit.json"),
        "forecast_validation": dict(model, metrics=forecast_metrics), "scenarios": scenarios, "reverse_stress": reverse,
        "source_provenance": source_provenance(), "limitations": limits,
        "research_conclusion": {"summary": f"Central, Downside and Severe scenarios allocate ${principal_loss[0] / 100:,.2f}, ${principal_loss[1] / 100:,.2f} and ${principal_loss[2] / 100:,.2f} of terminal note principal impairment. Class protection and payment timing depend on the specified borrower and recovery assumptions. The opening collateral residual receives a separate adverse loss treatment; other source discrepancies remain unresolved. Market-price data is required before a relative-value investment recommendation."}}
    if args.include_supplements:
        supplemental_path = ROOT / "output/extended_validation.json"
        supplemental = read(supplemental_path)
        expected = {"panel_sha256": identity["panel_sha256"],
                    "primary_protocol_sha256": identity["protocol_sha256"],
                    "credit_model_code_sha256": identity["model_code_sha256"],
                    "extended_validation_code_sha256": hash_file(ROOT / "credit_research/extended_validation.py"),
                    "runner_code_sha256": hash_file(ROOT / "scripts/run_extended_validation.py"),
                    "supplemental_protocol_sha256": hash_file(ROOT / "configs/supplemental_validation_protocol.json")}
        if supplemental.get("build_identity") != expected or not all(v is True for v in supplemental.get("checks", {}).values()) or not supplemental.get("checks"):
            raise ValueError("Supplemental validation is incomplete, failed, or stale")
        if supplemental.get("primary_model_changed") is not False or supplemental.get("scenario_assumptions_changed") is not False:
            raise ValueError("Supplemental analysis must leave the frozen primary model and scenarios unchanged")
        if supplemental.get("status") != "SUPPLEMENTAL_RETROSPECTIVE_AFTER_PRIMARY_TEST_INSPECTION":
            raise ValueError("Supplemental validation requires its explicit retrospective status")
        for split, evaluation in supplemental["locked_test_supplemental_evaluations"].items():
            for event in ("default", "prepayment"):
                refit = evaluation["methods"]["unchanged_primary_model"]["events"][event]
                frozen = model["evaluations"][split]["calibrated_multinomial"]["events"][event]
                for metric in ("brier", "auc", "average_precision", "balance_mae_cents"):
                    if refit[metric] != frozen[metric]:
                        raise ValueError("Supplemental refit does not reproduce the frozen primary metrics")
        pack["supplemental_validation"] = supplemental
        pack["supplemental_validation_sha256"] = hash_file(supplemental_path)
        pack["research_gates"]["credit_model"] = {"status": "IMPLEMENTED_WITH_LIMITATIONS",
            "evidence": "Frozen chronological/unseen-deal primary model; separate after-look cohort, fixed-segment and four expanding-time diagnostics; economic default timing and source allocations remain qualified"}
        review_path = ROOT / "data/rate_and_amendment_review.json"
        review = read(review_path)
        verification = review["supplemental_source_verification"]
        if verification["status"] != "PASS" or verification["source_manifest_sha256"] != hash_file(ROOT / review["supplemental_manifest"]):
            raise ValueError("Supplemental rate/legal sources are failed or stale")
        if pack["source_verification"]["source_manifest_sha256"] != hash_file(ROOT / "data/source_manifest.json"):
            raise ValueError("The frozen core source manifest changed after verification")
        if review["amendment_conclusion"] != "FINITE_PUBLIC_SEARCH_NO_TRANSACTION_AMENDMENT_IDENTIFIED":
            raise ValueError("An identified/pending amendment requires explicit term review")
        rate_checks = review["rate_review"]["checks"]
        if len(rate_checks) != 17 or any(c["status"] != "EXACT_MATCH" for c in rate_checks):
            raise ValueError("Official floating coupon reconstruction is incomplete or unequal")
        pack["rate_and_amendment_review"] = review
        pack["rate_and_amendment_review_sha256"] = hash_file(review_path)
        pack["research_gates"]["observed_floating_coupons"] = {"status": "PASS", "matches": 17,
            "evidence": "Official New York Fed30-day compounded averages plus executed69bp spread; issuer date labels remain erroneous"}
    for s in scenarios:
        if not all(s["checks"][x] for x in ("cash_conservation", "principal_conservation", "pool_conservation", "reserve_conservation", "horizon_closed")):
            raise AssertionError("A scenario conservation/closure check failed")
    path = ROOT / "output/platform_results.json"
    path.write_text(json.dumps(pack, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (ROOT / "output/platform_run_status.json").write_text(json.dumps({"status": "SUCCESS", "built_at": pack["generated_at"],
                "results_sha256": hash_file(path), "identity": identity}, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(path), "loan_months": len(panel), "historical_replay_periods": len(records),
                      "source_exceptions": len(source_exceptions), "latest_unmapped_cents": residual,
                      "scenario_note_losses_cents": principal_loss, "reverse_first_breach": reverse["first_breach"]}, indent=2), flush=True)
    if args.require_exact_reconciliation and (summary["unresolved_comparisons"] or replay_differences):
        raise SystemExit(2)


if __name__ == "__main__":
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    results = output / "platform_results.json"
    attempt = datetime.now(timezone.utc).isoformat()
    results.write_text(json.dumps({"status": "BUILDING", "attempt_started": attempt}), encoding="utf-8")
    (output / "platform_run_status.json").write_text(json.dumps({"status": "BUILDING", "attempt_started": attempt}), encoding="utf-8")
    try:
        main()
    except Exception as error:
        failed = {"status": "FAILED", "attempt_started": attempt, "error": str(error)}
        results.write_text(json.dumps(failed, indent=2), encoding="utf-8")
        (output / "platform_run_status.json").write_text(json.dumps(failed, indent=2), encoding="utf-8")
        raise
