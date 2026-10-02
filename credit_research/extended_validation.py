"""Supplemental cohort, segment and expanding-origin disclosure-risk study.

This analysis is specified after inspecting the primary test. It never changes
the primary model, its labels, its frozen split, or the scenario assumptions.
All features and censoring come from the existing disclosure_features adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .credit_models import (FEATURES, constant_probabilities, disclosure_features,
                            event_metrics, transition_probabilities)


COHORT_COLUMNS = ("credit_score", "age_months", "remaining_months", "disclosure_lag_months")
SEGMENTS = {
    "credit_score": ([620, 660, 720, 780], ["<=620", "620-660", "660-720", "720-780", ">780"]),
    "age_months": ([12, 24, 36], ["<=12", "12-24", "24-36", ">36"]),
    "remaining_months": ([12, 36, 60], ["<=12", "12-36", "36-60", ">60"]),
    "disclosure_lag_months": ([1, 2, 3], ["<=1", "1-2", "2-3", ">3"]),
    "delinquency_days": ([0, 30, 60, 90], ["current", "1-30", "31-60", "61-90", ">90"]),
    "interest_rate_pct": ([6, 9, 12, 15], ["<=6", "6-9", "9-12", "12-15", ">15"]),
}
FOLD_WINDOWS = (("2024-09-01", "2024-11-30"), ("2025-01-01", "2025-03-31"),
                ("2025-04-01", "2025-06-30"), ("2025-09-01", "2025-11-30"))


def band_ids(values: pd.Series, field: str) -> pd.Series:
    """Fixed right-closed bands; a missing observation has its own -1 band."""
    edges = [-np.inf, *SEGMENTS[field][0], np.inf]
    return pd.cut(pd.to_numeric(values, errors="coerce"), edges,
                  labels=False, include_lowest=True).fillna(-1).astype("int8")


def cohort_keys(rows: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({name: band_ids(rows[name], name) for name in COHORT_COLUMNS}, index=rows.index)


def validate_availability(rows: pd.DataFrame) -> None:
    if rows.empty:
        raise ValueError("A nonempty eligible disclosure sample is required")
    if not set(COHORT_COLUMNS).issubset(rows):
        raise ValueError("Prior-disclosure cohort features are missing")
    if "feature_acceptance_time" in rows:
        if "period_start" not in rows or rows.feature_acceptance_time.isna().any():
            raise ValueError("Feature availability dates must be complete")
        if not (rows.feature_acceptance_time <= rows.period_start).all():
            raise ValueError("A cohort feature was not public at its target origin")


def checked_probabilities(values, n: int) -> np.ndarray:
    p = np.asarray(values, dtype=float)
    if p.shape != (n, 3) or not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("Three finite competing probabilities are required per row")
    if not np.allclose(p.sum(axis=1), 1, rtol=0, atol=1e-10):
        raise ValueError("Competing probabilities must sum to one")
    return p


@dataclass
class SmoothedCohortBaseline:
    probabilities: pd.DataFrame
    overall: np.ndarray
    smoothing: float
    training_rows: int

    @classmethod
    def fit(cls, train: pd.DataFrame, *, smoothing: float = 100.0):
        validate_availability(train)
        if not np.isfinite(smoothing) or smoothing <= 0:
            raise ValueError("A fixed positive smoothing weight is required")
        y = train.outcome.to_numpy(dtype=int)
        if (y < 0).any() or (y > 2).any():
            raise ValueError("Unknown competing-event outcome")
        overall = constant_probabilities(train, 1)[0]
        keys = cohort_keys(train)
        keys["outcome"] = y
        counts = keys.groupby([*COHORT_COLUMNS, "outcome"], observed=True).size().unstack("outcome", fill_value=0)
        counts = counts.reindex(columns=[0, 1, 2], fill_value=0)
        probabilities = (counts + smoothing * overall) / (counts.sum(axis=1).to_numpy()[:, None] + smoothing)
        return cls(probabilities, overall, float(smoothing), len(train))

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        validate_availability(rows)
        index = pd.MultiIndex.from_frame(cohort_keys(rows))
        p = self.probabilities.reindex(index).to_numpy(dtype=float)
        unseen = ~np.isfinite(p).all(axis=1)
        p[unseen] = self.overall
        return checked_probabilities(p, len(rows))

    def describe(self) -> dict:
        return {"method": "Development empirical competing-event counts in fixed prior-FICO/age/remaining-term/disclosure-lag cells",
                "smoothing_pseudo_observations": self.smoothing,
                "overall_probabilities": self.overall.tolist(),
                "observed_cohort_cells": len(self.probabilities), "training_rows": self.training_rows,
                "unseen_cell": "Development-only overall probabilities", "missing_values": "Separate fixed band",
                "bands": {name: {"upper_edges": SEGMENTS[name][0], "labels": SEGMENTS[name][1]} for name in COHORT_COLUMNS}}


def primary_development_rows(rows: pd.DataFrame) -> pd.DataFrame:
    cutoff = pd.Timestamp("2025-06-30", tz="UTC")
    available = pd.Timestamp("2025-09-01", tz="UTC")
    return rows[(rows.deal_id == "CAOT-2024-2") & (rows.period_end <= cutoff)
                & (rows.acceptance_time < available)].copy()


def expanding_fold_frames(rows: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    origin = pd.Timestamp(start, tz="UTC")
    through = pd.Timestamp(end, tz="UTC")
    if origin > through or through >= pd.Timestamp("2026-02-01", tz="UTC"):
        raise ValueError("Supplemental expanding folds must remain before the frozen later test")
    older = rows[rows.deal_id == "CAOT-2024-2"]
    train = older[(older.period_end < origin) & (older.acceptance_time < origin)
                  & (older.period_end <= pd.Timestamp("2025-06-30", tz="UTC"))].copy()
    test = older[(older.period_start >= origin) & (older.period_end <= through)].copy()
    validate_availability(train)
    validate_availability(test)
    if not (train.acceptance_time < origin).all():
        raise AssertionError("A fold fitted an unfiled outcome")
    if set(train.outcome.unique()) != {0, 1, 2}:
        raise ValueError("An expanding fold needs all three competing outcomes")
    return train, test


def split_description(rows: pd.DataFrame) -> dict:
    return {"rows": len(rows), "loans": len(rows[["deal_id", "loan_id"]].drop_duplicates()),
            "period_start": rows.period_start.min().date().isoformat(),
            "period_end": rows.period_end.max().date().isoformat(),
            "max_label_acceptance": rows.acceptance_time.max().isoformat(),
            "max_feature_acceptance": rows.feature_acceptance_time.max().isoformat(),
            "outcome_counts": {str(k): int(v) for k, v in rows.outcome.value_counts().sort_index().items()}}


def segment_stability(train: pd.DataFrame, test: pd.DataFrame,
                      probabilities: dict[str, np.ndarray]) -> list[dict]:
    """Prior-feature composition and descriptive calibration by fixed segment."""
    validate_availability(train)
    validate_availability(test)
    probabilities = {name: checked_probabilities(p, len(test)) for name, p in probabilities.items()}
    records = []
    for field in SEGMENTS:
        train_bands, test_bands = band_ids(train[field], field), band_ids(test[field], field)
        train_counts = train_bands.value_counts()
        positions = pd.Series(np.arange(len(test)), index=test.index).groupby(test_bands, observed=True)
        for key, indices in positions:
            idx = indices.to_numpy(dtype=int)
            sample = test.iloc[idx]
            previous = train[train_bands == key]
            label = "missing" if key == -1 else SEGMENTS[field][1][int(key)]
            metrics = {}
            for cause, name in ((1, "default"), (2, "prepayment")):
                y = (sample.outcome.to_numpy(dtype=int) == cause).astype(int)
                previous_y = (previous.outcome.to_numpy(dtype=int) == cause).astype(int)
                methods = {}
                for method, p in probabilities.items():
                    estimate = p[idx, cause]
                    methods[method] = {"predicted_rate": float(estimate.mean()),
                        "calibration_gap": float(estimate.mean() - y.mean()),
                        "brier": float(np.mean((estimate - y) ** 2)),
                        "auc": float(roc_auc_score(y, estimate)) if len(np.unique(y)) > 1 else None}
                metrics[name] = {"events": int(y.sum()), "observed_rate": float(y.mean()),
                    "development_rate": float(previous_y.mean()) if len(previous_y) else None,
                    "methods": methods}
            train_n = int(train_counts.get(key, 0))
            records.append({"feature": field, "band_id": int(key), "segment": label,
                "development_rows": train_n, "test_rows": len(sample),
                "test_loans": len(sample[["deal_id", "loan_id"]].drop_duplicates()),
                "development_share": train_n / len(train), "test_share": len(sample) / len(test),
                "composition_change_percentage_points": (len(sample) / len(test) - train_n / len(train)) * 100,
                "beginning_exposure_cents": int(sample.begin_balance_cents.sum()), "events": metrics})
    return records


def run_extended_validation(panel: pd.DataFrame, primary_predict: Callable | None = None,
                            *, progress: Callable[[str], None] | None = None) -> dict:
    say = progress or (lambda _: None)
    say("Constructing prior-public-disclosure features using unchanged eligibility/censoring")
    rows = disclosure_features(panel)
    train = primary_development_rows(rows)
    validate_availability(train)
    cohort = SmoothedCohortBaseline.fit(train)
    evaluations = {}
    segments = {}
    for split, deal in (("later_months", "CAOT-2024-2"), ("unseen_deal", "CAOT-2025-2")):
        sample = rows[(rows.deal_id == deal) & (rows.period_start >= pd.Timestamp("2026-02-01", tz="UTC"))
                      & (rows.period_end <= pd.Timestamp("2026-08-31", tz="UTC"))].copy()
        validate_availability(sample)
        say(f"Scoring fixed cohort benchmark and segments: {split}, {len(sample):,} eligible observations")
        predictions = {"constant_baseline": constant_probabilities(train, len(sample)),
                       "delinquency_transition_baseline": transition_probabilities(train, sample),
                       "smoothed_cohort_baseline": cohort.predict(sample)}
        if primary_predict is not None:
            predictions["unchanged_primary_model"] = checked_probabilities(primary_predict(sample), len(sample))
        evaluations[split] = {"sample": split_description(sample),
                             "methods": {name: event_metrics(sample, p) for name, p in predictions.items()}}
        segments[split] = segment_stability(train, sample, predictions)
    folds = []
    for number, (start, end) in enumerate(FOLD_WINDOWS, 1):
        fold_train, fold_test = expanding_fold_frames(rows, start, end)
        say(f"Expanding fold {number}/{len(FOLD_WINDOWS)}: fit {len(fold_train):,}; score {len(fold_test):,}")
        model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                              StandardScaler(), LogisticRegression(C=1.0, max_iter=350, random_state=7))
        model.fit(fold_train[FEATURES], fold_train.outcome)
        if list(model.classes_) != [0, 1, 2]:
            raise AssertionError("Fold probability columns do not match event labels")
        fold_cohort = SmoothedCohortBaseline.fit(fold_train)
        predictions = {"constant_baseline": constant_probabilities(fold_train, len(fold_test)),
                       "delinquency_transition_baseline": transition_probabilities(fold_train, fold_test),
                       "smoothed_cohort_baseline": fold_cohort.predict(fold_test),
                       "uncalibrated_expanding_logistic": model.predict_proba(fold_test[FEATURES])}
        folds.append({"fold": number, "origin_date": start, "target_end": end,
                      "training": split_description(fold_train), "test": split_description(fold_test),
                      "preprocessing": "Imputer and scaler fitted anew on this fold's development rows only",
                      "calibration": "No future-period calibration; logistic probabilities are uncalibrated",
                      "methods": {name: event_metrics(fold_test, p) for name, p in predictions.items()}})
    return {"schema_version": 1, "status": "SUPPLEMENTAL_RETROSPECTIVE_AFTER_PRIMARY_TEST_INSPECTION",
            "primary_model_changed": False, "scenario_assumptions_changed": False,
            "target_definition": "First-observed default disclosure, voluntary payoff, or survival in the unchanged conditional eligible risk set",
            "development": split_description(train), "cohort_baseline": cohort.describe(),
            "locked_test_supplemental_evaluations": evaluations, "segment_stability": segments,
            "expanding_folds": folds,
            "checks": {"prior_feature_availability": bool((rows.feature_acceptance_time <= rows.period_start).all()),
                       "fold_labels_available_before_origin": all(pd.Timestamp(f["training"]["max_label_acceptance"]) < pd.Timestamp(f["origin_date"], tz="UTC") for f in folds),
                       "all_expanding_targets_before_primary_test": all(f["target_end"] < "2026-02-01" for f in folds),
                       "probability_conservation": True},
            "limitations": [
                "This supplemental protocol was specified after inspecting the original test. Its added test comparisons are descriptive, not a new untouched model-selection experiment.",
                "Expanding folds are retrospective development studies on one originator. The primary fitted model, labels and frozen test remain unchanged.",
                "Segment rates and calibration describe conditional observations with repeated loans. Small event counts and common-month dependence prevent unqualified significance claims.",
                "Development-versus-test composition changes reflect cohort seasoning, selection and vintages as well as possible performance drift; they are not a causal stability test.",
                "Aggregate event-exposure errors use actual beginning balances; they are not actual chargeoff, prepayment or investment cash errors.",
                "Economic default dates, recovery cash allocation and exact tape/certificate cash reconciliation remain subject to the separately documented source exceptions.",
                "No method must outperform every comparator to pass this diagnostic. Results are reported without selecting or refitting the primary model."
            ]}
