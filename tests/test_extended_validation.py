"""Independent smoothing, availability, fold and segment controls."""
import unittest

import numpy as np
import pandas as pd

from credit_research.extended_validation import (SmoothedCohortBaseline, band_ids,
    checked_probabilities, expanding_fold_frames, segment_stability)


def sample(outcomes=(0, 0, 1, 2)):
    n = len(outcomes)
    return pd.DataFrame({"deal_id": ["CAOT-2024-2"] * n, "loan_id": [f"L{x}" for x in range(n)],
        "credit_score": [700.] * n, "age_months": [15.] * n, "remaining_months": [40.] * n,
        "disclosure_lag_months": [2.] * n, "delinquency_days": [0.] * n, "interest_rate_pct": [8.] * n,
        "begin_balance_cents": [10_000] * n, "outcome": list(outcomes),
        "period_start": pd.to_datetime(["2024-08-01"] * n, utc=True),
        "period_end": pd.to_datetime(["2024-08-31"] * n, utc=True),
        "acceptance_time": pd.to_datetime(["2024-09-15"] * n, utc=True),
        "feature_acceptance_time": pd.to_datetime(["2024-07-15"] * n, utc=True)})


class ExtendedValidationTests(unittest.TestCase):
    def test_fixed_cohort_smoothing_and_unseen_fallback(self):
        train = sample()
        model = SmoothedCohortBaseline.fit(train, smoothing=10)
        # Global prior=(3,2,2)/7; cohort=(2,1,1), fixed10 pseudo-observations.
        expected = (np.array([2, 1, 1]) + 10 * np.array([3, 2, 2]) / 7) / 14
        np.testing.assert_allclose(model.predict(train)[0], expected)
        unknown = train.iloc[:1].copy()
        unknown["credit_score"] = 800
        np.testing.assert_allclose(model.predict(unknown)[0], np.array([3, 2, 2]) / 7)
        self.assertEqual(len(model.probabilities), 1)

    def test_current_outcomes_and_cash_do_not_change_benchmark_predictions(self):
        model = SmoothedCohortBaseline.fit(sample())
        test = sample()
        expected = model.predict(test)
        test["outcome"] = 2
        test["actualPrincipalCollectedAmount"] = 10 ** 12
        test["chargeoff_cents"] = 10 ** 12
        np.testing.assert_array_equal(model.predict(test), expected)

    def test_missing_features_have_separate_bands_and_boundaries_are_fixed(self):
        got = band_ids(pd.Series([np.nan, 620, 620.1, 780, 780.1]), "credit_score").tolist()
        self.assertEqual(got, [-1, 0, 1, 3, 4])
        train = sample()
        train.loc[0, "credit_score"] = np.nan
        model = SmoothedCohortBaseline.fit(train)
        self.assertEqual(len(model.probabilities), 2)
        self.assertTrue(np.isfinite(model.predict(train)).all())

    def test_unavailable_feature_is_rejected(self):
        train = sample()
        train.loc[0, "feature_acceptance_time"] = pd.Timestamp("2024-08-02", tz="UTC")
        with self.assertRaisesRegex(ValueError, "not public"):
            SmoothedCohortBaseline.fit(train)

    def test_expanding_origin_excludes_future_and_unfiled_labels(self):
        past = sample()
        past["period_start"] = pd.Timestamp("2024-06-01", tz="UTC")
        past["period_end"] = pd.Timestamp("2024-06-30", tz="UTC")
        past["acceptance_time"] = pd.Timestamp("2024-07-15", tz="UTC")
        past["feature_acceptance_time"] = pd.Timestamp("2024-05-15", tz="UTC")
        unfiled = past.iloc[:1].copy()
        unfiled["acceptance_time"] = pd.Timestamp("2024-08-02", tz="UTC")
        test = sample()
        rows = pd.concat([past, unfiled, test], ignore_index=True)
        train, heldout = expanding_fold_frames(rows, "2024-08-01", "2024-08-31")
        self.assertEqual(len(train), 4)
        self.assertEqual(len(heldout), 4)
        rows.loc[5:, "outcome"] = 1
        train_after, _ = expanding_fold_frames(rows, "2024-08-01", "2024-08-31")
        pd.testing.assert_frame_equal(train, train_after)
        with self.assertRaisesRegex(ValueError, "before the frozen later test"):
            expanding_fold_frames(rows, "2026-02-01", "2026-02-28")

    def test_segment_metrics_keep_probability_row_alignment(self):
        train = sample()
        test = sample((1, 0))
        test.index = [9, 2]
        test.loc[9, "credit_score"] = 600
        p = np.array([[.1, .8, .1], [.8, .1, .1]])
        report = segment_stability(train, test, {"model": p})
        low = next(r for r in report if r["feature"] == "credit_score" and r["segment"] == "<=620")
        self.assertEqual(low["events"]["default"]["events"], 1)
        self.assertAlmostEqual(low["events"]["default"]["methods"]["model"]["brier"], .04)
        self.assertAlmostEqual(low["events"]["default"]["methods"]["model"]["calibration_gap"], -.2)
        self.assertEqual(low["test_rows"], 1)
        self.assertEqual(low["development_rows"], 0)

    def test_probability_conservation_rejects_bad_matrix(self):
        for values in ([[.8, .2]], [[.8, .2, .2]], [[.8, -.1, .3]], [[np.nan, .1, .9]]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                checked_probabilities(values, 1)


if __name__ == "__main__":
    unittest.main()
