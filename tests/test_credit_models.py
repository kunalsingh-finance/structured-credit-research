import unittest
import pandas as pd
from credit_research.credit_models import disclosure_features, constant_probabilities, event_metrics


def row(period, accepted, **extra):
    start = pd.Timestamp(period + "-01", tz="UTC")
    d = dict(deal_id="x", loan_id="1", period_start=start,
             period_end=start + pd.offsets.MonthEnd(), acceptance_time=pd.Timestamp(accepted, tz="UTC"),
             begin_balance_cents=100000, end_balance_cents=95000, credit_score=700, orig_ltv_pct=90,
             interest_rate_pct=8, age_months=3, remaining_months=60, delinquency_days=0,
             first_default_event=0, prepayment_event=0, repurchase_event=0,
             chargeoff_cents=0, recovery_cents=0, prepayment_cents=0,
             principal_paid_cents=5000, interest_paid_cents=500)
    d.update(extra)
    return d


class CreditModelTests(unittest.TestCase):
    def test_uses_filing_available_before_origin(self):
        f = pd.DataFrame([row("2025-01", "2025-02-15", credit_score=600),
                          row("2025-02", "2025-03-15", credit_score=650),
                          row("2025-03", "2025-04-15", credit_score=800, first_default_event=1)])
        x = disclosure_features(f)
        self.assertEqual(len(x), 1)
        self.assertEqual(x.iloc[0].credit_score, 600)
        self.assertEqual(x.iloc[0].outcome, 1)
        self.assertEqual(x.iloc[0].disclosure_lag_months, 2)

    def test_current_outcomes_cannot_change_predictors(self):
        f = pd.DataFrame([row("2025-01", "2025-02-15"), row("2025-02", "2025-03-15"), row("2025-03", "2025-04-15")])
        a = disclosure_features(f)
        f.loc[2, ["credit_score", "end_balance_cents", "principal_paid_cents", "delinquency_days"]] = [200, 0, 100000, 180]
        b = disclosure_features(f)
        from credit_research.credit_models import FEATURES
        pd.testing.assert_frame_equal(a[FEATURES], b[FEATURES])

    def test_duplicate_events_rejected(self):
        f = pd.DataFrame([row("2025-01", "2025-02-15"), row("2025-01", "2025-02-15")])
        with self.assertRaises(ValueError):
            disclosure_features(f)

    def test_reinstated_prior_default_cannot_be_a_new_first_default(self):
        f = pd.DataFrame([row("2025-01", "2025-02-15", first_default_event=1),
                          row("2025-02", "2025-03-15"), row("2025-03", "2025-04-15")])
        self.assertTrue(disclosure_features(f).empty)

    def test_transfer_unknown_exit_censored(self):
        f = pd.DataFrame([row("2025-01", "2025-02-15", zero_balance_code=None),
                          row("2025-02", "2025-03-15", zero_balance_code=None),
                          row("2025-03", "2025-04-15", zero_balance_code="5")])
        self.assertTrue(disclosure_features(f).empty)

    def test_repurchase_not_prepay_training_label(self):
        f = pd.DataFrame([row("2025-01", "2025-02-15"), row("2025-02", "2025-03-15"),
                          row("2025-03", "2025-04-15", repurchase_event=1)])
        self.assertTrue(disclosure_features(f).empty)

    def test_metrics_balance_mae_computes_monthly_exposure(self):
        f = pd.DataFrame([row("2025-03", "2025-04-15"), row("2025-03", "2025-04-15", loan_id="2")])
        f["outcome"] = [1, 0]
        p = constant_probabilities(f, 2)
        metrics = event_metrics(f, p)
        self.assertEqual(metrics["events"]["default"]["observed_events"], 1)
        self.assertAlmostEqual(metrics["events"]["default"]["balance_mae_cents"], 20000)


if __name__ == "__main__":
    unittest.main()
