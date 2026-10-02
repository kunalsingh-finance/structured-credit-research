"""Bound the modeled impact of the disclosed OC ambiguity on fixed cash paths.

This separate, after-inspection diagnostic never changes executed deal terms,
primary research results or their exact-reconciliation gates. A hypothetical
reported-dollar target is a counterfactual, not a finding that it governs.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_research.cashflows import (
    CollateralPeriod, DealTerms, ScenarioState, distribute_period, run_scenario,
)
from credit_research.reconcile import parse_amount
from credit_research.waterfall import NOTES
from scripts.run_research import compare_replay

SSA_URL = "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm"
INDENTURE_URL = "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex41.htm"
CONSERVATION = ("cash_conservation", "principal_conservation", "pool_conservation", "reserve_conservation")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_inputs(root: Path) -> tuple[dict, dict, dict, dict]:
    """Reject stale or incomplete primary packs before any diagnostic is saved."""
    result_path = root / "output/platform_results.json"
    pack = read(result_path)
    status = read(root / "output/platform_run_status.json")
    require(status["status"] == "SUCCESS", "Primary generation is not SUCCESS")
    require(status["results_sha256"] == sha(result_path), "Primary results SHA mismatch")
    require(status["built_at"] == pack["generated_at"], "Primary generation timestamp mismatch")
    certificates_path = root / "data/actual_certificates.json"
    require(pack["build_identity"]["certificate_sha256"] == sha(certificates_path), "Certificate SHA mismatch")
    require(status["identity"] == pack["build_identity"], "Primary build identities disagree")
    certificates = read(certificates_path)
    require(len(certificates["certificates"]) == 46, "Complete 46-period certificate set required")
    for name, expected in pack["release_code_sha256"].items():
        require(sha(root / name) == expected, f"Stale primary research code: {name}")
    manifest_path = root / "data/source_manifest.json"
    manifest = read(manifest_path)
    matches = [s for s in manifest["sources"] if s["url"] == SSA_URL]
    require(len(matches) == 1, "Executed SSA source must be uniquely identified")
    source = matches[0]
    archive_path = root / source["archive_path"]
    archived = archive_path.read_bytes()
    original = gzip.decompress(archived)
    require(hashlib.sha256(archived).hexdigest() == source["sha256_archive"], "Executed SSA archive SHA mismatch")
    require(hashlib.sha256(original).hexdigest() == source["sha256_original_bytes"], "Executed SSA original SHA mismatch")
    require(len(original) == source["original_byte_count"], "Executed SSA original size mismatch")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", original.decode("utf-8"))))
    formula = re.search(r"Overcollateralization Target Amount.{0,30}shall mean, for any Distribution Date, an amount equal to 0\.75% of the Pool Balance as of the Cutoff Date", text)
    require(formula is not None, "Executed OC definition not independently located")
    require(pack["platform"]["initial_pool_cents"] == DealTerms().initial_pool_balance, "Initial pool conflicts with encoded executed terms")
    indentures = [s for s in manifest["sources"] if s["url"] == INDENTURE_URL]
    require(len(indentures) == 1, "Executed indenture source must be uniquely identified")
    indenture = indentures[0]
    indenture_path = root / indenture["archive_path"]
    indenture_archive = indenture_path.read_bytes()
    indenture_original = gzip.decompress(indenture_archive)
    require(hashlib.sha256(indenture_archive).hexdigest() == indenture["sha256_archive"], "Indenture archive SHA mismatch")
    require(hashlib.sha256(indenture_original).hexdigest() == indenture["sha256_original_bytes"], "Indenture original SHA mismatch")
    require(len(indenture_original) == indenture["original_byte_count"], "Indenture original size mismatch")
    indenture_text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", indenture_original.decode("utf-8"))))
    clause_start = indenture_text.find("(d) The principal of each Note shall be payable")
    clause = indenture_text[clause_start:clause_start + 1900] if clause_start >= 0 else ""
    require("in an aggregate amount" in clause and "equal to the sum" in clause
            and "to the Class A-2a Noteholders and the Class A-2b Noteholders, ratably" in clause,
            "Executed aggregate A2 allocation clause not independently located")
    identities = {
        "output/platform_results.json": sha(result_path),
        "output/platform_run_status.json": sha(root / "output/platform_run_status.json"),
        "data/actual_certificates.json": sha(certificates_path),
        "data/source_manifest.json": sha(manifest_path),
        source["archive_path"]: sha(archive_path),
        indenture["archive_path"]: sha(indenture_path),
        "scripts/analyze_oc_sensitivity.py": sha(root / "scripts/analyze_oc_sensitivity.py"),
        **pack["release_code_sha256"],
    }
    evidence = {"url": SSA_URL, "accession": source["accession"], "original_sha256": source["sha256_original_bytes"],
                "archive_sha256": source["sha256_archive"], "location": "Appendix A, Overcollateralization Target Amount",
                "formula": "0.75% of Pool Balance as of Cutoff Date", "independently_located_in_verified_original": True}
    evidence["aggregate_a2_allocation"] = {"url": INDENTURE_URL, "accession": indenture["accession"],
        "location": "Section 2.8(d)", "original_sha256": indenture["sha256_original_bytes"],
        "archive_sha256": indenture["sha256_archive"], "independently_located_in_verified_original": True,
        "rule": "Aggregate distribution principal across the five tiers; A2a and A2b share their class allocation ratably.",
        "rounding_convention": "Half-up to A2a once on the cumulative aggregate amount, with the remainder to A2b; the clause does not separately specify a fractional-cent convention."}
    return pack, certificates, identities, evidence


def reported_terms(initial_pool: int, reported_target: int) -> DealTerms:
    """Encode one hypothetical dollar target without changing any other rule."""
    with localcontext() as ctx:
        ctx.prec = 80
        rate = str(Decimal(reported_target) / initial_pool)
        require(int((Decimal(initial_pool) * Decimal(rate)).quantize(Decimal(1), rounding=ROUND_HALF_UP)) == reported_target,
                "Hypothetical rate does not reproduce the target in exact cents")
    return replace(DealTerms(), oc_rate=rate)


def historical_inputs(c: dict) -> tuple[ScenarioState, CollateralPeriod]:
    a, i = c["amounts"], c["replay_inputs"]
    state = ScenarioState(parse_amount(a["pool_begin"]), {n: parse_amount(i["note_begin"][n]) for n in NOTES},
                          parse_amount(a["reserve_begin"]), i["prior_distribution_date"])
    period = CollateralPeriod(c["distribution_date"], parse_amount(a["pool_end"]), parse_amount(a["principal_collected"]),
        parse_amount(a["interest_collected"]), recoveries=parse_amount(a["recoveries"]), defaults=parse_amount(a["defaults"]),
        repurchases=parse_amount(a["repurchases"]), investment_income=parse_amount(a["investment_income"]),
        reserve_interest=parse_amount(a["reserve_interest"]), floating_note_rate=i["floating_note_rate"], trustee_fee=parse_amount(a["trustee_fee"]))
    return state, period


def compare(c: dict, row: dict) -> list[dict]:
    adapter = dict(row)
    adapter.update(contractual_oc_target=row["oc_target"], servicing_fee=row["servicing_paid"],
                   total_note_interest=sum(row["interest"].values()), total_note_principal=sum(row["principal"].values()), **row["principal_tier_due"])
    return compare_replay(c, adapter)


def historical_sensitivity(pack: dict, certificates: dict, terms: DealTerms, target_delta: int) -> dict:
    reference = {c["collection_period_end"]: c for c in pack["certificates"]}
    rows = []
    for c in certificates["certificates"]:
        if c["deal_id"] != "CAOT-2025-2" or c["replay_inputs"]["prior_distribution_date"] < "2025-05-15":
            continue
        state, period = historical_inputs(c)
        _, base = distribute_period(state, period)
        require(base == reference[c["collection_period_end"]]["replay"], "Historical primary ledger reproduction failed")
        _, counter = distribute_period(state, period, terms)
        base_comparisons, counter_comparisons = compare(c, base), compare(c, counter)
        require(base_comparisons == reference[c["collection_period_end"]]["replay_comparison"], "Historical primary comparisons changed")
        due_delta = counter["principal_tier_due"]["regular"] - base["principal_tier_due"]["regular"]
        require(0 <= due_delta <= target_delta, "Fixed-state regular-principal Lipschitz check failed")
        require(all(counter["checks"][k] for k in CONSERVATION), "Historical counterfactual does not conserve")
        total_a2 = counter["principal"]["A2a"] + counter["principal"]["A2b"]
        weight_a2 = state.note_balances["A2a"] + state.note_balances["A2b"]
        # Exact rational half-up, independent of the waterfall's allocation helper.
        independent_a2a = (2 * total_a2 * state.note_balances["A2a"] + weight_a2) // (2 * weight_a2) if weight_a2 else 0
        require(counter["principal"]["A2a"] == independent_a2a, "Aggregate A2 allocation disagrees with independent rational rounding")
        rows.append({"collection_period_end": c["collection_period_end"], "distribution_date": c["distribution_date"],
                     "source_url": c["source_url"], "source_sha256": c["source_sha256"], "later_month": reference[c["collection_period_end"]]["holdout"],
                     "primary_ledger_reproduced_exactly": True, "regular_principal_due_delta_cents": due_delta,
                     "total_principal_paid_delta_cents": sum(counter["principal"].values()) - sum(base["principal"].values()),
                     "residual_distribution_delta_cents": counter["residual_distribution"] - base["residual_distribution"],
                     "primary_difference_count": sum(r["status"] != "PASS" for r in base_comparisons),
                     "counterfactual_difference_count": sum(r["status"] != "PASS" for r in counter_comparisons),
                     "counterfactual_remaining_differences": [r for r in counter_comparisons if r["status"] != "PASS"],
                     "independent_aggregate_a2_principal": {"total_cents": total_a2, "a2a_cents": independent_a2a,
                        "a2b_cents": total_a2 - independent_a2a, "matches_engine": True},
                     "counterfactual_conservation": {k: counter["checks"][k] for k in CONSERVATION}})
    require(len(rows) == 16, "All 16 post-stub historical periods required")
    return {"method": "Separate single-period comparisons reset to each certificate's reported opening note and reserve balances; no state propagation.",
            "period_count": len(rows), "later_month_count": sum(r["later_month"] for r in rows),
            "primary_difference_count": sum(r["primary_difference_count"] for r in rows),
            "counterfactual_difference_count": sum(r["counterfactual_difference_count"] for r in rows), "periods": rows}


def fixed_scenario_inputs(scenario: dict, origin: str) -> tuple[ScenarioState, list[CollateralPeriod]]:
    rows = scenario["monthly"]
    require(bool(rows), "Scenario has no ledger")
    first = rows[0]
    require(all(not r["accelerated"] and not r["cleanup_elected"] and r["trustee_paid"] == 0 and r["senior_expenses_paid"] == 0 for r in rows),
            "Scenario input adapter does not support elections or nonzero expenses")
    state = ScenarioState(first["pool_begin"], first["note_begin"], first["reserve_begin"], origin)
    periods = [CollateralPeriod(r["distribution_date"], r["pool_end"], r["principal_collected"], r["interest_collected"],
                 recoveries=r["recoveries"], defaults=r["defaults"], prepayments=r["prepayments"], repurchases=r["repurchases"],
                 investment_income=r["investment_income"], reserve_interest=r["reserve_interest"],
                 floating_note_rate=scenario["assumptions"]["floating_note_rate"]) for r in rows]
    return state, periods


def independent_value(tranche: dict, origin: str, discount_rate: str) -> tuple[Decimal, Decimal | None]:
    """Independently aggregate paid cash; never discount terminal loss as receipt."""
    with localcontext() as ctx:
        ctx.prec = 60
        cash_pv = Decimal(0)
        weighted_days = 0
        principal = 0
        for r in tranche["rows"]:
            days = (date.fromisoformat(r["distribution_date"]) - date.fromisoformat(origin)).days
            cash_pv += Decimal(r["principal_paid_cents"] + r["interest_paid_cents"]) / (1 + Decimal(discount_rate)) ** (Decimal(days) / Decimal("365.25"))
            principal += r["principal_paid_cents"]
            weighted_days += r["principal_paid_cents"] * days
        wal = Decimal(weighted_days) / principal / Decimal("365.25") if principal else None
        return +cash_pv, +wal if wal is not None else None


def decimal_text(value: Decimal | None, places: str = "0.00000001") -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal(places)), "f")


def propagated_sensitivity(pack: dict, terms: DealTerms) -> list[dict]:
    scenarios = []
    origin = pack["platform"]["valuation_date"]
    require({s["name"] for s in pack["scenarios"]} == {"Central", "Downside", "Severe"}, "All three frozen scenario paths required")
    for source in pack["scenarios"]:
        state, periods = fixed_scenario_inputs(source, origin)
        base = run_scenario(state, periods, terminal=True)
        require(base["monthly"] == source["monthly"] and base["checks"] == source["checks"], "Exact primary scenario reproduction failed")
        counter = run_scenario(state, periods, terms, terminal=True)
        require(all(counter["checks"][k] for k in CONSERVATION + ("horizon_closed",)), "Counterfactual horizon or conservation failed")
        metrics = []
        total_pv = Decimal(0)
        for b, a, saved in zip(base["tranches"], counter["tranches"], source["tranches"]):
            require(b["name"] == saved["name"] == a["name"], "Tranche alignment failed")
            for key in ("principal_paid_cents", "interest_paid_cents", "loss_cents", "interest_shortfall_cents", "maturity_failure"):
                require(b[key] == saved[key], f"Primary tranche result changed: {key}")
            pv_b, wal_b = independent_value(b, origin, str(source["assumptions"]["discount_rate"]))
            pv_a, wal_a = independent_value(a, origin, str(source["assumptions"]["discount_rate"]))
            opening = b["opening_balance_cents"]
            if opening:
                require(abs(float(pv_b / opening * 100) - saved["model_price_per_100"]) < 1e-9, "Independent primary PV disagrees")
            if b["repaid_principal_wal_years"] is not None:
                require(abs(float(wal_b) - b["repaid_principal_wal_years"]) < 1e-12, "Independent primary principal WAL disagrees")
            delta = pv_a - pv_b
            total_pv += delta
            metrics.append({"name": b["name"], "opening_balance_cents": opening,
                "principal_paid_delta_cents": a["principal_paid_cents"] - b["principal_paid_cents"],
                "interest_paid_delta_cents": a["interest_paid_cents"] - b["interest_paid_cents"],
                "terminal_principal_loss_delta_cents": a["loss_cents"] - b["loss_cents"],
                "unpaid_interest_claim_delta_cents": a["interest_shortfall_cents"] - b["interest_shortfall_cents"],
                "base_principal_loss_cents": b["loss_cents"], "counterfactual_principal_loss_cents": a["loss_cents"],
                "base_maturity_failure": b["maturity_failure"], "counterfactual_maturity_failure": a["maturity_failure"],
                "pv_delta_usd": decimal_text(delta / 100),
                "price_per_100_delta": decimal_text(delta / opening * 100 if opening else None, "0.000000000001"),
                "contractual_wal_delta_years": decimal_text(wal_a - wal_b if a["wal_years"] is not None and b["wal_years"] is not None else None, "0.000000000001"),
                "repaid_principal_wal_delta_years": decimal_text(wal_a - wal_b if wal_a is not None and wal_b is not None else None, "0.000000000001")})
        scenarios.append({"name": source["name"], "period_count": len(periods), "fixed_collateral_path_sha256": digest([p.__dict__ for p in periods]),
            "primary_monthly_ledger_reproduced_exactly": True, "independent_pv_and_wal_agree": True,
            "discount_rate": str(source["assumptions"]["discount_rate"]), "aggregate_note_pv_delta_usd": decimal_text(total_pv / 100),
            "note_cash_delta_cents": sum(r["principal_paid_delta_cents"] + r["interest_paid_delta_cents"] for r in metrics),
            "residual_distribution_delta_cents": sum(r["residual_distribution"] for r in counter["monthly"]) - sum(r["residual_distribution"] for r in base["monthly"]),
            "reserve_release_delta_cents": sum(r["reserve_release"] for r in counter["monthly"]) - sum(r["reserve_release"] for r in base["monthly"]),
            "primary_checks": base["checks"], "counterfactual_checks": counter["checks"], "tranches": metrics})
    return scenarios


def analyze(root: Path) -> dict:
    pack, certificates, identities, evidence = validate_inputs(root)
    targets = {parse_amount(c["expected"]["reported_oc_target"]) for c in certificates["certificates"] if c["deal_id"] == "CAOT-2025-2"}
    require(len(targets) == 1, "Reported OC target must be constant across the observed target certificates")
    reported = targets.pop()
    initial = pack["platform"]["initial_pool_cents"]
    # Independent integer half-up arithmetic for the exact 75/10,000 fraction.
    formula_target = (initial * 75 + 5_000) // 10_000
    delta = reported - formula_target
    require(delta > 0, "This diagnostic requires reported OC above the formula")
    terms = reported_terms(initial, reported)
    historical = historical_sensitivity(pack, certificates, terms, delta)
    scenarios = propagated_sensitivity(pack, terms)
    # Avoid saving a mixed generation if any authoritative input changed mid-run.
    require(validate_inputs(root)[2] == identities, "Inputs changed while the diagnostic was running")
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "status": "CONDITIONAL_SENSITIVITY_COMPLETED",
        "input_sha256": identities, "primary_generated_at": pack["generated_at"], "legal_evidence": evidence,
        "target_comparison": {"initial_pool_cents": initial, "executed_fraction": "0.0075", "executed_formula_target_cents": formula_target,
                              "reported_target_cents": reported, "difference_cents": delta, "counterfactual_equivalent_fraction": terms.oc_rate},
        "historical_reset_sensitivity": historical, "propagated_fixed_scenarios": scenarios,
        "strict_primary_gates_unchanged": pack["research_gates"],
        "interpretation": "The modeled consequence is quantified conditionally on these fixed collateral paths; no authoritative governing-rule resolution or exact source reconciliation is established.",
        "limits": ["Specified after inspection of primary results; this is a legal-input sensitivity, not a new withheld forecast evaluation.",
                   "Only the OC target is varied. Initial pool, reserve minimum, cleanup threshold, collateral cash, fees, elections and all other legal terms stay fixed.",
                   "Historical periods reset to reported opening balances. Adding their period deltas does not represent a state-propagated historical cash path.",
                   "Scenario states propagate independently from one common origin. All supplied collateral and recovery cash paths are identical between alternatives.",
                   "The two alternative endpoints do not prove a uniform bound over intermediate targets, arbitrary paths, rate scenarios or trigger changes.",
                   "No source cash allocation, collateral eligibility correction, amendment or issuer explanation is inferred. Exact primary differences are retained.",
                   "Small price effects on these paths do not establish investment materiality, a rating, investment alpha or executable market value."]}


def render_report(result: dict) -> str:
    target = result["target_comparison"]
    history = result["historical_reset_sensitivity"]
    def money(cents: int) -> str:
        sign = "-" if cents < 0 else ""
        whole, fraction = divmod(abs(cents), 100)
        return f"{sign}${whole:,}.{fraction:02d}"
    lines = [
        "# Conditional OC sensitivity", "",
        "The executed OC formula remains the primary rule. This separate diagnostic measures the consequence of substituting the reported dollar target under identical collateral cash assumptions. It does not decide which target legally governs, reconcile the loan tapes or change any primary release gate.", "",
        f"Generated `{result['generated_at']}` from primary results `{result['primary_generated_at']}`; primary SHA-256 `{result['input_sha256']['output/platform_results.json']}`. Machine evidence: [oc_sensitivity.json](../output/oc_sensitivity.json).", "",
        "## Authoritative formula and hypothetical alternative", "",
        f"The [executed sale and servicing agreement, Appendix A]({SSA_URL}) defines OC as 0.75% of cutoff Pool Balance. Original and compressed source bytes are independently rehashed before calculation. Integer rational half-up arithmetic gives **{money(target['executed_formula_target_cents'])}** on documented cutoff principal of **{money(target['initial_pool_cents'])}**. Certificates report **{money(target['reported_target_cents'])}**, a **{money(target['difference_cents'])}** increase.", "",
        "The counterfactual varies only the OC target. It encodes the reported dollars as an equivalent decimal fraction while keeping initial pool, reserve minimum, cleanup threshold, coupons, fees, elections and collateral paths fixed. This hypothetical fraction is not an amendment or an alternative authoritative contract interpretation.", "",
        "## Historical comparisons reset to each certificate", "",
        f"All {history['period_count']} post-stub primary ledgers reproduce exactly, including {history['later_month_count']} separately identified later months. Each comparison starts with that certificate's reported opening notes and reserve; state is reset for the next period. Primary comparisons retain {history['primary_difference_count']} differences. With the hypothetical reported target, {history['counterfactual_difference_count']} differences remain.", "",
        "For fixed opening balances and all other inputs, regular principal due is a clipped affine function of the OC target. Its change lies between zero and the target change. All historical comparisons satisfy that exact-cent local bound. This local due-amount result does not bound a state-propagated PV, credit loss or arbitrary trigger path. Historical period deltas cannot be summed to represent one propagated history.", "",
        "The [executed indenture, Section 2.8(d)](" + INDENTURE_URL + ") allocates aggregate distribution principal across the five tiers and shares A2 principal ratably. The diagnostic independently checks cumulative A2 allocation using opening class weights and exact rational half-up arithmetic. Fractional-cent half-up allocation is an explicit modeled convention; the clause does not itself specify a fractional-cent convention. Reported distributions are comparisons, never calculation inputs beyond the expressly labeled target alternative.", "",
        "## Propagated fixed scenario paths", "",
        "Each alternative starts from the same September 15, 2026 note, reserve and collateral state. Cash flows, defaults, recovery timing, principal collections, interest collections and flat floating coupon are identical between alternatives. Note balances and interest claims then propagate independently. All primary monthly ledgers and controls reproduce exactly; both alternatives conserve cash, note principal, pool principal and reserves and reach a closed horizon.", "",
        "PV discounts only paid cash at the common 8% effective annual assumption on actual distribution dates. Decimal calculations independently agree with primary prices and paid-principal WAL. Terminal economic impairment and unpaid claims are not discounted as cash receipts.", "",
        "| Fixed path | Periods | Aggregate note PV change (USD) | Note cash change | Terminal principal-loss change | Maturity flags change |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for scenario in result["propagated_fixed_scenarios"]:
        loss_delta = scenario["counterfactual_checks"]["terminal_principal_losses_cents"] - scenario["primary_checks"]["terminal_principal_losses_cents"]
        flag_change = scenario["counterfactual_checks"]["maturity_failures"] != scenario["primary_checks"]["maturity_failures"]
        lines.append(f"| {scenario['name']} | {scenario['period_count']} | {scenario['aggregate_note_pv_delta_usd']} | {money(scenario['note_cash_delta_cents'])} | {money(loss_delta)} | {'Yes' if flag_change else 'No'} |")
    lines += ["", "The machine output reports each class's paid principal, interest, unpaid claims, principal loss, full-repayment WAL, paid-principal WAL and price effects separately. WAL remains unavailable for impaired or uncompleted classes. The two endpoints quantify consequences on these fixed paths; they do not establish a uniform bound across intermediate targets, arbitrary collateral paths, yield assumptions or other trigger states.", "",
              "## Reproduce and inspect freshness", "", "```powershell", "python scripts/analyze_oc_sensitivity.py", "python scripts/analyze_oc_sensitivity.py --verify-only", "```", "",
              "The script rejects unfinished primary generation, results/version mismatch, changed certificates, stale research code, corrupted executed-source bytes, unsupported scenario elections/expenses, failed exact primary reproduction and inputs changed during computation. Verification also rejects saved evidence or this report if it no longer matches the authoritative inputs. It runs no fitting, downloading or full-panel projection.", "",
              "Exact source cash and eligibility differences and the governing OC discrepancy still require authoritative evidence. A small modeled effect under specified assumptions does not establish investment materiality or completed financial validation.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/oc_sensitivity.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/OC_SENSITIVITY.md")
    parser.add_argument("--verify-only", action="store_true", help="Reject an existing sensitivity whose authoritative inputs changed")
    args = parser.parse_args()
    if args.verify_only:
        saved = read(args.output)
        require(saved["input_sha256"] == validate_inputs(ROOT)[2], "Saved sensitivity has stale input hashes")
        require(args.report.read_text(encoding="utf-8") == render_report(saved), "Saved sensitivity report does not match machine evidence")
        print("Saved conditional OC sensitivity is bound to the current frozen inputs")
        return
    result = analyze(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(result), encoding="utf-8")
    print(f"Saved conditional OC sensitivity: {args.output}")
    print("Exact primary gates are unchanged; this diagnostic does not resolve governing terms")


if __name__ == "__main__":
    main()
