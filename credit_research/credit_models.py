"""Disclosure-aware competing-event credit research.

Features are taken only from an earlier filing accepted before the target
collection month starts. Eligibility is the subsequently observed beginning
exposure, so the evaluation estimates conditional monthly hazards, not a live
prediction of the entire unknown fleet. This distinction is exported alongside
the metrics. No random row split or contemporaneous payment field is used.
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["log_balance", "credit_score", "orig_ltv_pct", "interest_rate_pct",
            "age_months", "remaining_months", "delinquency_days", "disclosure_lag_months"]
REQUIRED = ["deal_id", "loan_id", "period_start", "period_end", "acceptance_time",
            "begin_balance_cents", "end_balance_cents", "credit_score", "orig_ltv_pct",
            "interest_rate_pct", "age_months", "remaining_months", "delinquency_days",
            "first_default_event", "prepayment_event", "repurchase_event", "chargeoff_cents",
            "recovery_cents", "prepayment_cents", "principal_paid_cents", "interest_paid_cents"]


def load_panel(path: str | Path) -> pd.DataFrame:
    with sqlite3.connect(path) as db:
        fields = {r[1] for r in db.execute("PRAGMA table_info(loan_month)")}
        missing = set(REQUIRED) - fields
        if missing:
            raise ValueError(f"Panel missing required columns: {sorted(missing)}")
        extra = [x for x in ("maturity_event", "zero_balance_code") if x in fields]
        chunks = []
        for chunk in pd.read_sql_query("SELECT " + ",".join(REQUIRED + extra) + " FROM loan_month", db, chunksize=150000):
            for field in ("period_start", "period_end", "acceptance_time"):
                chunk[field] = pd.to_datetime(chunk[field], utc=True)
            chunks.append(chunk)
        frame = pd.concat(chunks, ignore_index=True)
    frame["deal_id"] = frame.deal_id.astype("category")
    frame["loan_id"] = frame.loan_id.astype("category")
    if frame.duplicated(["deal_id", "loan_id", "period_end"]).any():
        raise ValueError("Duplicate deal/loan/period rows cannot enter credit modeling")
    frame["period_start"] = pd.to_datetime(frame.period_start, utc=True)
    frame["period_end"] = pd.to_datetime(frame.period_end, utc=True)
    frame["acceptance_time"] = pd.to_datetime(frame.acceptance_time, utc=True)
    if frame[["period_start", "period_end", "acceptance_time"]].isna().any().any():
        raise ValueError("Missing source dates prevent point-in-time evaluation")
    return frame.sort_values(["deal_id", "loan_id", "period_end"]).reset_index(drop=True)


def disclosure_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return lagged source features plus outcomes, with unavailable rows excluded."""
    if frame.duplicated(["deal_id", "loan_id", "period_end"]).any():
        raise ValueError("Duplicate loan months")
    frame = frame.sort_values(["deal_id", "loan_id", "period_end"]).copy()
    g = frame.groupby(["deal_id", "loan_id"], sort=False, observed=True)
    terminal = frame.first_default_event.fillna(0) + frame.prepayment_event.fillna(0) + frame.repurchase_event.fillna(0)
    if "maturity_event" in frame:
        terminal += frame.maturity_event.fillna(0)
    prior_terminal = terminal.groupby([frame.deal_id, frame.loan_id], sort=False, observed=True).cumsum() - terminal > 0
    censor = frame.end_balance_cents.isna()
    if "zero_balance_code" in frame:
        codes = frame.zero_balance_code.fillna("").astype(str)
        censor |= codes.str.contains(r"(?:^|\|)(?:2|5|99)(?:\||$)", regex=True)
    result = frame[["deal_id", "loan_id", "period_start", "period_end", "acceptance_time",
                    "begin_balance_cents", "end_balance_cents", "first_default_event",
                    "prepayment_event", "repurchase_event", "chargeoff_cents", "recovery_cents",
                    "prepayment_cents", "principal_paid_cents", "interest_paid_cents"]].copy()
    for name in FEATURES:
        result[name] = np.nan
    result["feature_acceptance_time"] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")
    result["feature_period_end"] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")
    assigned = np.zeros(len(frame), dtype=bool)
    # Monthly disclosures normally arrive 15 days into the next month. Four
    # periods also handles one missing filing without quietly ignoring its lag.
    for lag in (1, 2, 3, 4):
        previous = g.shift(lag)
        accepted = pd.to_datetime(previous.acceptance_time, utc=True)
        end = pd.to_datetime(previous.period_end, utc=True)
        months = ((frame.period_start.dt.year - end.dt.year) * 12
                  + frame.period_start.dt.month - end.dt.month)
        use = (~assigned & (accepted <= frame.period_start).fillna(False).to_numpy()
               & (end < frame.period_start).fillna(False).to_numpy()
               & (previous.end_balance_cents > 0).fillna(False).to_numpy())
        if not use.any():
            continue
        result.loc[use, "log_balance"] = np.log1p(previous.loc[use, "end_balance_cents"].astype(float) / 100)
        for name in ("credit_score", "orig_ltv_pct", "interest_rate_pct", "delinquency_days"):
            result.loc[use, name] = pd.to_numeric(previous.loc[use, name], errors="coerce")
        result.loc[use, "age_months"] = pd.to_numeric(previous.loc[use, "age_months"], errors="coerce") + months[use]
        result.loc[use, "remaining_months"] = np.maximum(0, pd.to_numeric(previous.loc[use, "remaining_months"], errors="coerce") - months[use])
        result.loc[use, "disclosure_lag_months"] = months[use]
        result.loc[use, "feature_acceptance_time"] = accepted[use]
        result.loc[use, "feature_period_end"] = end[use]
        assigned[use] = True
    result = result.loc[assigned & ~prior_terminal.to_numpy() & ~censor.to_numpy() & (frame.begin_balance_cents.fillna(0).to_numpy() > 0)
                        & ~frame.repurchase_event.fillna(0).astype(bool).to_numpy()].copy()
    if ((result.first_default_event.astype(bool)) & result.prepayment_event.astype(bool)).any():
        raise ValueError("Default and prepayment must be mutually exclusive first events")
    result["outcome"] = np.where(result.first_default_event.astype(bool), 1,
                                  np.where(result.prepayment_event.astype(bool), 2, 0))
    if not (pd.to_datetime(result.feature_acceptance_time, utc=True) <= result.period_start).all():
        raise AssertionError("A feature was unavailable at the start of its target month")
    return result


def constant_probabilities(train: pd.DataFrame, n: int) -> np.ndarray:
    counts = np.bincount(train.outcome.astype(int), minlength=3).astype(float) + 1
    return np.tile(counts / counts.sum(), (n, 1))


def transition_probabilities(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    def bucket(x):
        return pd.cut(x.fillna(-1), [-2, -0.5, 0, 30, 60, 90, np.inf], labels=False).astype(int)
    lookup = {}
    overall = constant_probabilities(train, 1)[0]
    for key, rows in train.groupby(bucket(train.delinquency_days), observed=True):
        counts = np.bincount(rows.outcome.astype(int), minlength=3).astype(float)
        # A fixed 100-loan prior prevents a tiny delinquency cell claiming certainty.
        lookup[key] = (counts + 100 * overall) / (counts.sum() + 100)
    return np.vstack([lookup.get(key, overall) for key in bucket(test.delinquency_days)])


def event_metrics(rows: pd.DataFrame, probabilities: np.ndarray) -> dict:
    p = np.clip(probabilities, 1e-9, 1 - 1e-9)
    p /= p.sum(axis=1, keepdims=True)
    y = rows.outcome.to_numpy(dtype=int)
    out = {"n": len(rows), "log_loss": float(log_loss(y, p, labels=[0, 1, 2])), "events": {}}
    balance = rows.begin_balance_cents.to_numpy(dtype=float)
    for label, name in ((1, "default"), (2, "prepayment")):
        binary = (y == label).astype(int)
        prediction = p[:, label]
        bins = pd.DataFrame({"actual": binary, "predicted": prediction})
        bins["bin"] = pd.qcut(bins.predicted.rank(method="first"), min(10, len(bins)), labels=False)
        calibration = [{"bin": int(k) + 1, "n": len(v), "predicted": float(v.predicted.mean()),
                        "observed": float(v.actual.mean())} for k, v in bins.groupby("bin")]
        per_month = []
        for month, index in rows.groupby(rows.period_end.dt.strftime("%Y-%m")).indices.items():
            b = balance[index]
            per_month.append({"period": month, "predicted_balance_cents": int(round(np.dot(prediction[index], b))),
                              "observed_event_balance_cents": int(np.dot(binary[index], b)),
                              "eligible_balance_cents": int(b.sum())})
        out["events"][name] = {
            "observed_events": int(binary.sum()), "observed_rate": float(binary.mean()),
            "predicted_rate": float(prediction.mean()), "brier": float(brier_score_loss(binary, prediction)),
            "auc": float(roc_auc_score(binary, prediction)) if len(np.unique(binary)) > 1 else None,
            "average_precision": float(average_precision_score(binary, prediction)) if binary.sum() else None,
            "calibration": calibration, "monthly_balance_predictions": per_month,
            "balance_mae_cents": float(np.mean([abs(v["predicted_balance_cents"] - v["observed_event_balance_cents"]) for v in per_month]))}
    return out


def cluster_uncertainty(rows: pd.DataFrame, model_p: np.ndarray, baseline_p: np.ndarray, draws: int = 200) -> dict:
    """Loan-cluster bootstrap retains dependence across repeated observations."""
    sums = pd.DataFrame({"loan": rows.deal_id.astype(str) + ":" + rows.loan_id.astype(str), "n": 1})
    for label, event in ((1, "default"), (2, "prepayment")):
        y = (rows.outcome.to_numpy() == label).astype(float)
        sums[event + "_actual"] = y
        sums[event + "_brier"] = (y - model_p[:, label]) ** 2
        sums[event + "_brier_lift"] = (y - baseline_p[:, label]) ** 2 - (y - model_p[:, label]) ** 2
    group = sums.groupby("loan", sort=False).sum()
    values = group.to_numpy(dtype=float)
    random = np.random.default_rng(20261002)
    draws_out = []
    for _ in range(draws):
        total = values[random.integers(0, len(values), len(values))].sum(axis=0)
        draws_out.append(total[1:] / total[0])
    bounds = np.quantile(np.array(draws_out), [.025, .975], axis=0)
    return {"method": "200 fixed-seed loan-cluster bootstrap draws, percentile 95% interval",
            "loans": len(group), "intervals": {key: {"lower": float(bounds[0, i]), "upper": float(bounds[1, i])}
                         for i, key in enumerate(group.columns[1:])}}


def recovery_cohorts(panel: pd.DataFrame, deal: str = "CAOT-2024-2", horizon: int = 12) -> dict:
    """Observed recoveries of seasoned defaults, with missing loan rows censored."""
    f = panel[panel.deal_id == deal]
    first = f[(f.first_default_event == 1) & (f.chargeoff_cents > 0)][["loan_id", "period_end", "chargeoff_cents"]].copy()
    first.columns = ["loan_id", "default_period", "default_principal"]
    if first.loan_id.duplicated().any():
        raise ValueError("Default cohort contains repeated first-default events")
    cutoff = f.period_end.max() - pd.DateOffset(months=horizon)
    first = first[first.default_period <= cutoff]
    recovery = f[["loan_id", "period_end", "recovery_cents"]].merge(first, on="loan_id", how="inner")
    recovery["lag"] = ((recovery.period_end.dt.year - recovery.default_period.dt.year) * 12
                       + recovery.period_end.dt.month - recovery.default_period.dt.month)
    recovery = recovery[(recovery.lag >= 0) & (recovery.lag <= horizon)]
    counts = recovery.groupby("loan_id", observed=True).lag.nunique()
    complete = counts[counts == horizon + 1].index
    censored_count = len(first) - len(complete)
    recovery = recovery[recovery.loan_id.isin(complete)]
    first = first[first.loan_id.isin(complete)]
    denominator = int(first.default_principal.sum())
    if denominator <= 0:
        return {"available": False, "reason": "No fully observed seasoned default cohorts", "censored_loans": censored_count}
    flows = recovery.groupby("lag").recovery_cents.sum().reindex(range(horizon + 1), fill_value=0)
    cumulative = flows.cumsum()
    total = int(flows.sum())
    lag = int(next((i for i, amount in cumulative.items() if amount >= total / 2), horizon)) if total > 0 else horizon
    return {"available": True, "deal": deal, "loans": len(first), "censored_loans": censored_count,
            "observation_months": horizon, "default_principal_cents": denominator,
            "recovery_cents": total, "observed_recovery_fraction": total / denominator,
            "median_recovery_flow_lag_months": lag,
            "curve": [{"lag_months": int(i), "period_recovery_cents": int(flows[i]),
                       "cumulative_recovery_fraction": float(cumulative[i] / denominator)} for i in flows.index],
            "limitation": "Realized twelve-month recovery fraction for complete seasoned default records. It is not ultimate recovery; late flows and other-originator behavior remain uncertain."}


def train_credit_models(panel: pd.DataFrame, training_deal: str = "CAOT-2024-2", target_deal: str = "CAOT-2025-2") -> tuple[dict, object]:
    rows = disclosure_features(panel)
    old = rows[rows.deal_id == training_deal]
    months = sorted(old.period_end.unique())
    if len(months) < 9:
        raise ValueError("At least nine eligible older-deal periods are required for chronological development/calibration/test")
    # Written before the first fit; an embargo separates label publication from
    # each later evaluation segment. Never move boundaries to improve a result.
    calibration_start = pd.Timestamp("2025-09-01", tz="UTC")
    test_start = pd.Timestamp("2026-02-01", tz="UTC")
    # Fit only labels already filed at the next segment's first collection date.
    cal_origin = calibration_start.replace(day=1)
    test_origin = test_start.replace(day=1)
    train = old[(old.period_end <= pd.Timestamp("2025-06-30", tz="UTC")) & (old.acceptance_time < cal_origin)]
    calibration = old[(old.period_end >= calibration_start) & (old.period_end <= pd.Timestamp("2025-11-30", tz="UTC"))
                      & (old.acceptance_time < test_origin)]
    test = old[old.period_end >= test_start]
    if min(len(train), len(calibration), len(test)) < 100 or len(train.outcome.unique()) < 3:
        raise ValueError("Insufficient observed competing events for independent credit evaluation")
    model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                          StandardScaler(), LogisticRegression(C=1.0, max_iter=350, random_state=7))
    model.fit(train[FEATURES], train.outcome)
    # A development-only multinomial calibrator adjusts base rates; no test
    # labels or target-deal labels enter fitting or calibration.
    calibrator = LogisticRegression(C=1.0, max_iter=300, random_state=7)
    cal_p = np.clip(model.predict_proba(calibration[FEATURES]), 1e-9, 1)
    if len(calibration.outcome.unique()) != 3:
        raise ValueError("Calibration requires all competing outcomes")
    calibrator.fit(np.log(cal_p), calibration.outcome)
    def predict(x):
        return calibrator.predict_proba(np.log(np.clip(model.predict_proba(x[FEATURES]), 1e-9, 1)))
    predict.estimators = {"model": model, "calibrator": calibrator}
    unseen = rows[(rows.deal_id == target_deal) & (rows.period_start >= test_origin)]
    evaluations = {}
    for name, sample in (("later_months", test), ("unseen_deal", unseen)):
        if sample.empty:
            raise ValueError(f"Missing {name} holdout")
        model_p = predict(sample)
        baseline_p = constant_probabilities(train, len(sample))
        evaluations[name] = {
            "constant_baseline": event_metrics(sample, baseline_p),
            "delinquency_transition_baseline": event_metrics(sample, transition_probabilities(train, sample)),
            "calibrated_multinomial": event_metrics(sample, model_p),
            "uncertainty": cluster_uncertainty(sample, model_p, baseline_p)}
    splits = {}
    for name, sample in (("training", train), ("calibration", calibration), ("later_months", test), ("unseen_deal", unseen)):
        splits[name] = {"n": len(sample), "period_start": sample.period_start.min().date().isoformat(),
                        "period_end": sample.period_end.max().date().isoformat(),
                        "max_label_acceptance": sample.acceptance_time.max().isoformat(),
                        "deals": sorted(sample.deal_id.unique().tolist())}
    # Prospective rates use the latest *disclosed* target fleet, with the feature
    # state available in that report. Actual September/October performance is
    # not silently invented if August is the latest reported collection period.
    target = panel[panel.deal_id == target_deal]
    latest = target[target.period_end == target.period_end.max()].copy()
    defaulted = set(target.loc[target.first_default_event.astype(bool), "loan_id"])
    active = latest[latest.end_balance_cents > 0].copy()
    active["previously_defaulted"] = active.loan_id.isin(defaulted)
    future = pd.DataFrame(index=active.index)
    future["log_balance"] = np.log1p(active.end_balance_cents / 100)
    for feature in FEATURES[1:-1]:
        future[feature] = pd.to_numeric(active[feature], errors="coerce")
    source_as_of = latest.acceptance_time.max()
    forecast_start = (source_as_of + pd.offsets.MonthBegin()).normalize()
    snapshot_end = latest.period_end.iloc[0]
    forecast_lag = (forecast_start.year - snapshot_end.year) * 12 + forecast_start.month - snapshot_end.month
    future["age_months"] += forecast_lag
    future["remaining_months"] = np.maximum(0, future.remaining_months - forecast_lag)
    future["disclosure_lag_months"] = forecast_lag
    forecast = predict(future)
    weights = active.end_balance_cents.to_numpy(dtype=float)
    never_defaulted = ~active.previously_defaulted.to_numpy()
    if not never_defaulted.any():
        raise ValueError("No first-event eligible loans remain in the disclosed target pool")
    default_rate = float(np.average(forecast[never_defaulted, 1], weights=weights[never_defaulted]))
    prepay_rate = float(np.average(forecast[never_defaulted, 2], weights=weights[never_defaulted]))
    total_event = default_rate + prepay_rate
    total_hazard = -math.log1p(-total_event)
    default_hazard = total_hazard * default_rate / total_event if total_event else 0
    prepay_hazard = total_hazard * prepay_rate / total_event if total_event else 0
    period_aggregates = target.groupby("period_end").agg(defaults=("chargeoff_cents", "sum"), recoveries=("recovery_cents", "sum"))
    # Censored recovery ratio is an explicit observed-flow benchmark, never an
    # estimated ultimate recovery for recently defaulted loans.
    recovery_ratio = float(period_aggregates.recoveries.sum() / period_aggregates.defaults.sum()) if period_aggregates.defaults.sum() else .3
    coefficients = model[-1].coef_.tolist()
    result = {
        "method": "regularized multinomial logistic competing-event model with development-only calibration",
        "features": FEATURES, "splits": splits, "evaluations": evaluations,
        "baseline_probabilities": constant_probabilities(train, 1)[0].tolist(),
        "recovery_cohorts": recovery_cohorts(panel),
        "training_periods": f"{splits['training']['period_start']} to {splits['training']['period_end']}",
        "holdout_periods": f"{splits['later_months']['period_start']} to {splits['later_months']['period_end']}",
        "eligible_loan_months": len(rows), "excluded_loan_months": len(panel) - len(rows),
        "coefficients_standardized": coefficients,
        "forecast": {"period_end": latest.period_end.iloc[0].date().isoformat(),
                     "as_of": latest.acceptance_time.max().isoformat(), "active_loans": len(active),
                     "target_collection_period_start": forecast_start.date().isoformat(),
                     "disclosure_lag_months": forecast_lag,
                     "previously_defaulted_positive_balance_loans": int(active.previously_defaulted.sum()),
                     "previously_defaulted_balance_cents": int(weights[~never_defaulted].sum()),
                     "reinstated_default_hazard_multiplier": 2.0,
                     "balance_cents": int(weights.sum()), "monthly_default_probability": default_rate,
                     "monthly_prepayment_probability": prepay_rate,
                     "annual_default_rate": -math.expm1(-12 * default_hazard),
                     "annual_prepayment_rate": -math.expm1(-12 * prepay_hazard),
                     "annual_default_probability": default_rate / total_event * (1 - (1 - total_event) ** 12) if total_event else 0,
                     "annual_prepayment_probability": prepay_rate / total_event * (1 - (1 - total_event) ** 12) if total_event else 0,
                     "observed_recovery_flow_ratio": recovery_ratio,
                     "weighted_apr": float(np.average(active.interest_rate_pct.fillna(0), weights=weights)) / 100,
                     "weighted_remaining_months": float(np.average(active.remaining_months.fillna(0), weights=weights))},
        "limitations": [
            "Conditional monthly hazards use observed beginning exposure for eligibility and dollar-error evaluation. They do not predict the undisclosed live fleet's eligibility.",
            "All predictors come from an earlier accession accepted before the target collection month. Current-period payments, ending balances and chargeoffs are outcomes only.",
            "The later-month and unseen-deal tests are withheld from fitting and calibration; the two deals are from the same originator and do not establish other-originator generalization.",
            "Public reporting delays leave a gap between the latest collateral snapshot and today's date. Scenario projections start at that snapshot and include the unreported interval.",
            "Observed aggregate recovery/default flow ratio is censored and mixes vintages. Ultimate recoveries and recovery timing remain scenario assumptions.",
            "Logistic hazards have constant modeled monthly rates in the aggregate runoff scenarios; no claim of causal macroeconomic stress forecasting is made.",
            "Reinstated positive-balance loans remain in collateral. Their redefault hazard is an explicit two-times central hazard assumption; a first-default model cannot estimate redefault.",
            "Loan-cluster bootstrap intervals condition on fitted models and observed calendar months. They exclude macroeconomic, parameter-fitting and calibration uncertainty."
        ]}
    return result, predict


def write_model_results(panel_path: str | Path, output_path: str | Path) -> dict:
    result, _ = train_credit_models(load_panel(panel_path))
    Path(output_path).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result
