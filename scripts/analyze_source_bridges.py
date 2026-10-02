"""Build a source-cited exception register without changing the loan panel.

Inputs are exact certificate extraction, committed panel summaries, the
full-corpus balance audit and read-only event timing audit. Alternative default
aggregations are diagnostic hypotheses, not transformations used to force fit.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def cents(value):
    return int(Decimal(value) * 100)


def main():
    summary = load("data/panel_summary.json")
    certificates = load("data/actual_certificates.json")["certificates"]
    diagnostics = load("data/source_bridge_diagnostics.json")
    event_audit = load("data/default_observation_audit.json")
    manifest = load("data/source_manifest.json")["sources"]
    verified = load("data/source_verification.json")
    by_period = {(c["deal_id"], c["collection_period_end"]): c for c in certificates}
    by_diagnostic = {(d["deal_id"], d["period_end"]): d for d in diagnostics}
    assert sum(d["rows"] for d in diagnostics) == summary["row_count"] == event_audit["counts"]["rows"]
    assert len(by_period) == len(by_diagnostic) == len(summary["comparisons"]) == 46
    assert verified["status"] == "PASS" and verified["source_count"] == len(manifest)

    def source_reference(source):
        return {k: source[k] for k in ("kind", "url", "archive_path", "sha256_original_bytes",
                                      "acceptance_time", "accession") if k in source}

    explanatory = [s for s in manifest if s["kind"] == "asset_explanatory"]
    legal = [s for s in manifest if s["kind"] == "executed_legal" and s["url"].endswith("dex991.htm")]
    schema = [s for s in manifest if s["kind"] == "official_xml_schema"]
    assert len(explanatory) == 46 and len({s["sha256_original_bytes"] for s in explanatory}) == 1
    evidence = {
        "EX103": {"source": source_reference(explanatory[-1]), "identical_original_hash_across_months": 46,
                  "items": {
                      "3(f)(15)": "Other principal adjustment is B-E-principal-chargeoff; after October 2021 only net increases, negative, principally returned principal and reinstated chargeoffs.",
                      "3(f)(18)": "Total actual paid is payment receipts while not charged off, net reversals and floored at zero.",
                      "3(f)(19)": "Interest is period receipts net reversals and floored at zero.",
                      "3(f)(20)": "Principal includes net receipts and certain noncash reductions including bankruptcy; net negative amounts reported zero.",
                      "3(f)(21)": "Other collections are net of reversals and floored at zero.",
                      "3(f)(22)": "Servicer advance field omitted when none made.",
                      "3(i)(1)": "Uncollected principal charged off during the reporting period.",
                      "3(i)(2)": "Receipts after earlier chargeoff; excess period reversals reported zero.",
                      "3(k),3(k)(1)": "Repossession indicator is vehicle repossessed and account not reinstated; disposition proceeds are net fees/expenses, with no explicit monthly reset statement.",
                  }},
        "XSD": {"sources": [source_reference(s) for s in schema],
                "extracted_file": "data/raw/schema/eis_ABS_AutoLoanAssetData.xsd",
                "items": {"3(f)(19-22)": "Official generic schema defines collected/advanced amounts, but contains no separate noncash, clipped-reversal or certificate-allocation fields.",
                          "3(f)(24)": "Zero-balance effective date has month precision; zeroBalanceCode is optional/repeatable, with code 4 charged off and code 1 prepaid/matured.",
                          "3(i)(1-2),3(k)(1)": "Chargeoff, post-chargeoff receipts and net disposition proceeds are distinct fields, not an additive certificate cash bridge."}},
        "SSA": {"sources": [source_reference(s) for s in legal],
                "sections": {"4.3": "Receivable receipts including liquidation/repossessed sale receipts are allocated using Simple Interest Method; purchased-receivable receipts and Supplemental Servicing Fees excluded.",
                             "3.8,4.8": "Ordinary monthly servicing fee is paid separately; net physical deposits do not change gross accounting.",
                             "4.4": "Optional Simple Interest Advances and their reimbursement have specific cash treatment.",
                             "AppendixA/AvailableCollections": "Includes specified obligor payments, net liquidation proceeds, Collection Account income, purchase amounts, refund proceeds and advances, subject to exclusions.",
                             "AppendixA/DefaultedReceivable,PrincipalBalance": "Default is month-end 120 days past due, repossessed-and-sold or servicer-uncollectible, excluding purchased loans; principal of defaulted/purchased receivables is zero at month-end."}},
    }

    gate_counts = {}
    for comparison in summary["comparisons"]:
        for check in comparison["checks"]:
            counts = gate_counts.setdefault(check["check"], Counter())
            counts[check["status"]] += 1
    periods = []
    for comparison in summary["comparisons"]:
        key = comparison["deal_id"], comparison["period_end"]
        certificate, diagnostic = by_period[key], by_diagnostic[key]
        target = cents(certificate["amounts"]["defaults"])
        alternatives = []
        for name, observed in (
            ("all_reported_chargeoff_flows", comparison["statistics"]["raw_chargeoff_cents"]),
            ("first_observed_default_chargeoff_flows", diagnostic["first_default_chargeoffs"]),
            ("first_observed_default_beginning_principal", diagnostic["first_default_begin_balance"]),
            ("chargeoffs_with_effective_month_equal_reporting_month", diagnostic["effective_month_chargeoffs"]),
            ("all_chargeoffs_plus_all_other_principal_adjustments", diagnostic["net_chargeoff_adjustments"]),
        ):
            alternatives.append({"candidate": name, "observed_cents": observed,
                                 "reported_cents": target, "residual_cents": observed - target,
                                 "status": "NUMERIC_MATCH_ONLY" if observed == target else "DOES_NOT_RECONCILE",
                                 "used_as_forced_cash_input": False})
        certificate_count = re.search(r"\|\s*(\d+)\s*\|\s*\$", certificate["source_rows"]["76"]["label"])
        periods.append({"deal_id": key[0], "period_end": key[1],
                        "loan_tape_sources": [source_reference(s) for s in manifest if s["kind"] == "loan_tape" and (s["deal_id"], s["report_period"]) == key],
                        "certificate_url": certificate["source_url"], "certificate_sha256": certificate["source_sha256"],
                        "strict_checks": comparison["checks"], "default_candidates": alternatives,
                        "first_observed_default_count": diagnostic["first_defaults"],
                        "certificate_default_count": int(certificate_count[1]) if certificate_count else None,
                        "row_balance_identity_failures": diagnostic["balance_identity_failures"],
                        "row_balance_identity_residual_cents": diagnostic["balance_identity_residual_cents"]})

    def exception(id, gate, status, reason, controlling, required, numbers=None):
        return {"id": id, "gate": gate, "status": status, "reason": reason,
                "controlling_evidence": controlling, "required_to_resolve": required,
                "quantitative_example": numbers or {}, "residual_used_as_input": False}

    exceptions = [
        exception("POOL-001", "Outstanding principal and count", "UNRESOLVED_SOURCE_MAPPING",
                  "Strictly positive loan balances economically remove customer credit balances; this resolves eligibility/sign handling but does not reconstruct the issuer collateral ledger. Count matches in 22/46 periods, ending principal in 0/46. No public loan-level exclusion/adjustment schedule reconciles the residual.",
                  ["SSA/AppendixA/PrincipalBalance", "XSD/3(f)(16,24)", "EX103/3(f)(15)"],
                  "Issuer tape-to-eligible-pool ledger with loan IDs, credit-balance handling and principal adjustments as of the same month end.",
                  {"deal_id": "CAOT-2025-2", "period_end": "2026-08-31", "positive_loans": 47562, "certificate_loans": 47562,
                   "positive_end_cents": 74497025215, "certificate_end_cents": 74497076416, "residual_cents": -51201,
                   "negative_credit_balance_cents": -13320, "positive_begin_residual_cents": -49987}),
        exception("CASH-001", "Principal cash", "NON_IDENTIFIABLE_FROM_DISCLOSED_FIELDS",
                  "The issuer expressly includes noncash principal reductions and nets/clips certain reversals in actualPrincipalCollected. Neither XML nor EX103 separates their values. Exact B-E-P-CO-Adj identity verifies arithmetic, not the cash/noncash partition. Individual residual causation remains unknown.",
                  ["EX103/3(f)(15,18,20)", "XSD/3(f)(15,18,20)", "SSA/4.3,AppendixA/AvailableCollections"],
                  "Per-loan gross principal receipts, reversals, noncash/bankruptcy reductions and certificate cash allocation, including issuer aggregate adjustment totals.",
                  {"deal_id": "CAOT-2025-2", "period_end": "2026-08-31", "raw_cents": 2950961488, "certificate_cents": 2950205828, "residual_cents": 755660}),
        exception("CASH-002", "Finance-charge cash", "NON_IDENTIFIABLE_FROM_DISCLOSED_FIELDS",
                  "Tape interest is net of reversals and has zero flooring; legal cash includes specified allocations and exclusions. No public field quantifies clipped negative interest. Advances, aggregate recovery or servicing fee substitutions do not form an exact supported bridge. The gap already exists in an initial month with no chargeoff/recovery flows or advances.",
                  ["EX103/3(f)(19,22)", "XSD/3(f)(19)", "SSA/3.8,4.3,4.4,4.8,AppendixA/AvailableCollections"],
                  "Unclipped interest receipts/reversals and issuer finance-charge allocations by loan, including liquidation interest and applicable exclusions.",
                  {"deal_id": "CAOT-2025-2", "period_end": "2026-08-31", "raw_cents": 612423281, "certificate_cents": 617378569, "residual_cents": -4955288,
                   "certificate_liquidation_interest_cents": 111066, "certificate_advances_cents": 0,
                   "CAOT_2024_2_first_month_interest_residual_cents": -128864542}),
        exception("LOSS-001", "New legal default loss", "UNRESOLVED_EVENT_TIMING_AND_REINSTATEMENT_BRIDGE",
                  "Raw positive chargeoffs can recur after a loan's first observed default; the issuer effective month can predate first observed reporting. Chargeoff-only, first-observed-only, effective-month-only, beginning-exposure and chargeoff-plus-adjustment candidates all fail examples. Other adjustments mix returned payments with reinstatements, so adding every adjustment to chargeoffs is unsupported.",
                  ["EX103/3(f)(15),3(i)(1)", "XSD/3(f)(24),3(i)(1)", "SSA/AppendixA/DefaultedReceivable,PrincipalBalance"],
                  "Issuer monthly new-default/reinstatement/rechargeoff ledger with exact effective dates, recognition-month rules and segregated principal adjustment causes.",
                  {"deal_id": "CAOT-2025-2", "period_end": "2026-08-31", "raw_cents": 165952654, "certificate_cents": 130941789, "residual_cents": 35010865,
                   "first_observed_chargeoff_cents": 131992487, "first_observed_chargeoff_residual_cents": 1050698,
                   "chargeoff_plus_adjustment_cents": 130127629, "chargeoff_plus_adjustment_residual_cents": -814160,
                   "first_observed_count": 73, "certificate_count": 74}),
        exception("CASH-003", "Recovery cash", "NON_IDENTIFIABLE_FROM_DISCLOSED_FIELDS",
                  "RecoveredAmount is a period post-chargeoff flow with stated reversal flooring, whereas certificate recoveries aggregate allocated liquidation proceeds. Exact issuer month/cash-reversal/allocation mapping is absent. Retained disposition proceeds overlap recovery flows and cannot be added to recoveries.",
                  ["EX103/3(i)(2),3(k)(1)", "XSD/3(i)(2),3(k)(1)", "SSA/4.3,AppendixA/LiquidationProceeds,AvailableCollections"],
                  "Dated post-default receipts and reversals, liquidation expense deductions and allocated principal/interest portions linked to certificate rows 17b/18b/77.",
                  {"deal_id": "CAOT-2025-2", "period_end": "2026-08-31", "raw_cents": 35066699, "certificate_cents": 34571596, "residual_cents": 495103}),
        exception("REPO-001", "Disposition proceeds temporal classification", "RESOLVED_AS_RETAINED_HISTORY_NOT_ADDITIVE_MONTHLY_CASH",
                  "August 2026 contains 379 unchanged nonzero disposition values totaling $4,375,741.27 from July, and direct repo/recovery overlap on identical loans. Treating total repossessedProceeds as a fresh monthly flow would reuse old sales and double count some recovery cash. Net change alone still cannot allocate all monthly receipts.",
                  ["EX103/3(k)(1)", "XSD/3(k)(1)", "output/independent_repo_repeat_2025-2_2026-08.json"],
                  "Dated sale transactions and receipt allocation needed before disposition amounts can enter any new monthly cash bridge.",
                  {"current_disposition_sum_cents": 469737478, "unchanged_prior_disposition_cents": 437574127,
                   "unchanged_count": 379, "new_nonzero_count": 37, "net_change_cents": 28419864}),
        exception("EVENT-001", "First observed versus legal default timing", "QUALIFIED_DISCLOSURE_LABEL",
                  "First-default flags are once per loan and based on first reported chargeoff/code 4, not transient repossession. All first-default and code 4 rows have nonpositive ending balances. Of 4,526 first observed defaults, 1,032 carry earlier effective months and 19 occur at first-tape boundaries; legal default month cannot be assumed equal to observed month. Later reinstatements remain exposure and do not create a second first default.",
                  ["XSD/3(f)(24)", "SSA/AppendixA/DefaultedReceivable,PrincipalBalance", "data/default_observation_audit.json"],
                  "Earlier tapes or issuer exact default-recognition dates and reinstatement ledger to recover legal event timing; keep disclosure-event modeling and availability restrictions explicit.",
                  event_audit["counts"] | {"unique_reinstated_loans": event_audit["unique_positive_balance_loans_after_observed_default"]}),
        exception("SOURCE-001", "Negative recovery versus explanatory rule", "UNRESOLVED_SOURCE_DESCRIPTION_CONTRADICTION",
                  "September 2024 contains a signed negative recoveredAmount totaling -$3,599.68 in an ACTIVE-status group although the identical EX103 describes zero flooring of excess reversals. The original signed values remain intact; descriptive prose is not authority to clamp conflicting source facts.",
                  ["EX103/3(i)(2)", "output/independent_cash_bridge_2024-2_2024-09.json"],
                  "Issuer clarification/correction of negative recovery and reinstatement-period reporting, preserving original and amended versions.",
                  {"deal_id": "CAOT-2024-2", "period_end": "2024-09-30", "negative_recovery_cents": -359968}),
        exception("CERT-001", "Stale 2025 certificate headers", "CHRONOLOGY_RESOLVED_WITH_SOURCE_EXCEPTION",
                  "Two certificates report stale April collection labels and May distribution labels while actual 10-D metadata and dated June/July exhibit filenames identify consecutive May/June collections and June 16/July 15 payments. Parser preserves every original header and records chronology method.",
                  ["data/actual_certificates.json/source_header,source_exceptions", "data/source_manifest.json/report_period"],
                  "A corrected issuer exhibit would resolve the conflicting source labels; existing chronology inference remains explicitly attributed."),
        exception("CERT-002", "Missing retired A2 reported interest", "AGGREGATE_RESOLVED_CLASS_VALUE_UNRESOLVED",
                  "2024-2 January–March 2026 retired A2 interest cells contain original U+FFFD replacement characters. Missing individual classes are preserved; aggregate note interest is exact reported total note deposits less reported class principal. A missing class is not silently converted to zero.",
                  ["data/actual_certificates.json/missing_reported_interest_classes,source_rows45q"],
                  "Issuer corrected class-interest cells required for complete class-level replay comparison."),
    ]
    for item in exceptions:
        example = item["quantitative_example"]
        if "raw_cents" in example:
            assert example["raw_cents"] - example["certificate_cents"] == example["residual_cents"]
        if "positive_end_cents" in example:
            assert example["positive_end_cents"] - example["certificate_end_cents"] == example["residual_cents"]
    result = {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "INVESTIGATED_STRICT_SOURCE_GATE_REMAINS_FAILED",
        "row_count": summary["row_count"], "period_count": len(periods),
        "verified_original_and_archive_sources": len(manifest),
        "strict_tape_to_certificate_checks": {"total": sum(sum(c.values()) for c in gate_counts.values()),
                                             "failed": summary["unresolved_comparisons"],
                                             "by_gate": {k: dict(v) for k, v in gate_counts.items()}},
        "resolved_row_balance_identity": {"tested_rows": sum(d["rows"] for d in diagnostics),
                                          "failures": sum(d["balance_identity_failures"] for d in diagnostics),
                                          "residual_cents": sum(d["balance_identity_residual_cents"] for d in diagnostics)},
        "resolved_transformations": [
            "Signed monetary source values retained exactly as cents; missing optional fields stay NULL distinct from explicit zero.",
            "Strictly positive balances define observable outstanding loan eligibility, removing customer credits without arbitrary normalization.",
            "First observed defaults are counted once; later chargeoff/recovery flows remain period source facts; missing rows do not imply payoff.",
            "Explicit zero chargeoff permits otherwise-valid prepay; prior defaults and code 3/4 exclude voluntary payoff; maturity requires positive beginning exposure.",
            "Repossessed disposition values recognized as retained history with recovery overlap, not added as fresh monthly cash.",
            "Stale certificate date labels preserved while dated filenames/actual reportPeriod identify chronology; missing class cells not zero-filled.",
        ],
        "evidence": evidence, "exceptions": exceptions, "periods": periods,
        "independent_audit": "docs/INDEPENDENT_CASH_BRIDGE_AUDIT.md",
        "investment_use_gate": "FAIL: exact source cash, eligible collateral and legal default reconciliation requires issuer ledger or corrected disclosures. An immediate-full-loss adverse convention on the latest balance residual is not a mathematical present-value bound across all waterfall paths and does not bound other unresolved fields.",
    }
    (ROOT / "data/source_exception_register.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(exceptions)} investigated exceptions, {len(periods)} periods, {summary['unresolved_comparisons']} strict differences", flush=True)


if __name__ == "__main__":
    main()
