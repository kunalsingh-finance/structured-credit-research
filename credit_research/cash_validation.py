"""Frozen-model, disclosure-origin collateral forecasts against later certificates.

This is separately scored cash forecasting, unlike the conditional loan hazard
evaluation. Origin exposure is the latest publicly filed fleet. The unreported
bridge is projected, not replaced with the later known beginning balance.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from .credit_models import FEATURES, recovery_cohorts
from .projections import make_cohorts, project_collateral, distribution_date
from .reconcile import parse_amount


def annual_inputs(d, p):
    total = float(d + p)
    if not math.isfinite(total) or d < 0 or p < 0 or not 0 <= total < 1:
        raise ValueError("Invalid competing probabilities")
    hazard = -math.log1p(-total)
    return (-math.expm1(-12 * hazard * d / total), -math.expm1(-12 * hazard * p / total)) if total else (0, 0)


def evaluate_cash_forecasts(panel, certificates, predict, baseline):
    # Recovery fitting also obeys availability; no 2026 recovery outcome may
    # enter a forecast for a February2026 collection period.
    recovery_sample = panel[panel.acceptance_time < pd.Timestamp("2026-01-01", tz="UTC")]
    recovery = recovery_cohorts(recovery_sample)
    if not recovery.get("available"):
        raise ValueError("No development-only seasoned recovery cohorts for cashflow validation")
    rr = recovery["observed_recovery_fraction"]
    lag = max(1, recovery["median_recovery_flow_lag_months"])
    by_key = {(c["deal_id"], c["collection_period_end"]): c for c in certificates}
    predictions = []
    for deal in ("CAOT-2024-2", "CAOT-2025-2"):
        fleet = panel[panel.deal_id == deal]
        for target in (c for c in certificates if c["deal_id"] == deal and "2026-02-01" <= c["collection_period_end"] <= "2026-08-31"):
            origin = pd.Timestamp(target["collection_period_start"], tz="UTC")
            known = fleet[(fleet.acceptance_time <= origin) & (fleet.period_end < origin)]
            snapshot_end = known.period_end.max()
            snapshot = known[known.period_end == snapshot_end].copy()
            active = snapshot[snapshot.end_balance_cents > 0].copy()
            previous_default = set(known.loc[known.first_default_event == 1, "loan_id"])
            active["previously_defaulted"] = active.loan_id.isin(previous_default)
            gap = (origin.year - snapshot_end.year) * 12 + origin.month - snapshot_end.month
            if gap < 1 or active.empty:
                raise ValueError("Missing publicly available historical origin fleet")
            features = pd.DataFrame(index=active.index)
            features["log_balance"] = np.log1p(active.end_balance_cents / 100)
            for feature in FEATURES[1:-1]:
                features[feature] = pd.to_numeric(active[feature], errors="coerce")
            features["age_months"] += gap
            features["remaining_months"] = np.maximum(0, features.remaining_months - gap)
            features["disclosure_lag_months"] = gap
            probabilities = predict(features)
            eligible = ~active.previously_defaulted.to_numpy()
            weights = active.end_balance_cents.to_numpy(dtype=float)
            md = float(np.average(probabilities[eligible, 1], weights=weights[eligible]))
            mp = float(np.average(probabilities[eligible, 2], weights=weights[eligible]))
            cohorts, _ = make_cohorts(active, int(weights.sum()))
            source_certificate = by_key[(deal, snapshot_end.date().isoformat())]
            if pd.Timestamp(source_certificate["acceptance_time"]) > origin:
                raise ValueError("Origin cash calibration certificate was not public at the forecast origin")
            origin_apr = snapshot.interest_rate_pct.fillna(snapshot.interest_rate_pct.dropna().median()) / 100
            interest_proxy = float((snapshot.begin_balance_cents.clip(lower=0) * origin_apr / 12).sum())
            collection_ratio = parse_amount(source_certificate["amounts"]["interest_collected"]) / interest_proxy
            factor = min(1.0, collection_ratio)
            expected_distribution = distribution_date(source_certificate["distribution_date"], gap)
            if expected_distribution != target["distribution_date"]:
                raise ValueError("Projected final payment month differs from the target servicing period")
            for method, d, p in (("constant_baseline", baseline[1], baseline[2]), ("calibrated_model", md, mp)):
                annual_d, annual_p = annual_inputs(d, p)
                _, rows = project_collateral(cohorts, source_certificate["distribution_date"],
                         annual_default_rate=annual_d, annual_prepayment_rate=annual_p,
                         recovery_rate=rr, recovery_lag_months=lag, interest_collection_factor=factor,
                         horizon_months=gap, require_closed=False)
                # A fully prepaid fleet may close before the target period.
                # Its later cash and ending collateral are then zero.
                forecast = rows[-1] if len(rows) == gap else {key: 0 for key in (
                    "default_cents", "scheduled_principal_cents", "prepayment_cents", "interest_cents", "pool_end_cents")}
                quantities = {"gross_defaults": (forecast["default_cents"], target["amounts"]["defaults"]),
                              "principal_collections": (forecast["scheduled_principal_cents"] + forecast["prepayment_cents"], target["amounts"]["principal_collected"]),
                              "interest_collections": (forecast["interest_cents"], target["amounts"]["interest_collected"]),
                              "ending_pool": (forecast["pool_end_cents"], target["amounts"]["pool_end"])}
                predictions.append({"deal_id": deal, "target_period": target["collection_period_end"],
                         "origin_date": origin.date().isoformat(), "source_period": snapshot_end.date().isoformat(),
                         "source_accepted": snapshot.acceptance_time.max().isoformat(), "bridge_months": gap,
                         "forecast_distribution_date": expected_distribution,
                         "assumptions": {"annual_default_rate": annual_d, "annual_prepayment_rate": annual_p,
                              "recovery_fraction": rr, "recovery_lag_months": lag,
                              "interest_collection_factor": factor, "uncapped_collection_ratio": collection_ratio,
                              "reinstated_default_hazard_multiplier": 2.0},
                         "method": method, "metrics": {name: {"forecast_cents": int(value), "observed_cents": parse_amount(actual),
                                       "error_cents": int(value) - parse_amount(actual)} for name, (value, actual) in quantities.items()}})
    scores = []
    for deal in ("CAOT-2024-2", "CAOT-2025-2"):
        for quantity in ("gross_defaults", "principal_collections", "interest_collections", "ending_pool"):
            errors = {}
            for method in ("constant_baseline", "calibrated_model"):
                sample = [r for r in predictions if r["deal_id"] == deal and r["method"] == method]
                errors[method] = float(np.mean([abs(r["metrics"][quantity]["error_cents"]) for r in sample]))
            scores.append({"deal_id": deal, "quantity": quantity, "unit": "USD cents", "months": len(sample),
                           "baseline_mae_cents": errors["constant_baseline"], "model_mae_cents": errors["calibrated_model"]})
    return {"method": "Frozen conditional model mapped to a publicly known origin fleet and projected across the unreported bridge; compared to future actual servicing cash",
            "recovery_benchmark": recovery, "monthly": predictions, "scores": scores,
            "limitations": ["Both models use the same disclosed term/APR annuity and collection-factor assumptions; only event hazards differ.",
                "Scores measure certificate cash errors and expose source-taxonomy/model error together. They do not resolve loan-tape cash reconciliation.",
                "Recoveries from defaults before the forecast origin are not included in these short-window diagnostics; recovery forecasting is therefore not scored.",
                "Reported origin collateral is the mapped positive tape balance; small certificate mismatches remain visible rather than normalized away.",
                "Model superiority is metric-specific. A smaller default error does not establish better principal, interest or investment outcomes."]}
