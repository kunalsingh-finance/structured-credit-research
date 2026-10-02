import copy
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from credit_research.cash_validation import evaluate_cash_forecasts


class CashForecastOriginTests(unittest.TestCase):
    def fixtures(self):
        rows, certificates = [], []
        for deal in ("CAOT-2024-2", "CAOT-2025-2"):
            for end, acceptance, balance in (("2025-12-31", "2026-01-15", 12000000),
                                              ("2026-01-31", "2026-02-15", 99999999)):
                rows.append(dict(deal_id=deal, loan_id="1", period_end=end,
                    acceptance_time=acceptance, begin_balance_cents=13000000,
                    end_balance_cents=balance, first_default_event=0,
                    credit_score=650, orig_ltv_pct=95, interest_rate_pct=12,
                    age_months=12, remaining_months=24, delinquency_days=0))
            for start, end, acceptance, distribution in (
                    ("2025-12-01", "2025-12-31", "2026-01-15", "2026-01-15"),
                    ("2026-02-01", "2026-02-28", "2026-03-15", "2026-03-16")):
                certificates.append(dict(deal_id=deal, collection_period_start=start,
                    collection_period_end=end, acceptance_time=acceptance + "T12:00:00Z",
                    distribution_date=distribution, amounts=dict(defaults="100.00",
                        principal_collected="5000.00", interest_collected="1000.00",
                        pool_end="110000.00")))
        panel = pd.DataFrame(rows)
        for column in ("period_end", "acceptance_time"):
            panel[column] = pd.to_datetime(panel[column], utc=True)
        return panel, certificates

    def evaluate(self, panel, certificates):
        seen = []
        def predict(features):
            seen.append(features.copy())
            return np.tile([.97, .01, .02], (len(features), 1))
        def recovery(sample):
            self.assertTrue((sample.acceptance_time < pd.Timestamp("2026-01-01", tz="UTC")).all())
            return dict(available=True, observed_recovery_fraction=.3,
                        median_recovery_flow_lag_months=2)
        with patch("credit_research.cash_validation.recovery_cohorts", side_effect=recovery):
            result = evaluate_cash_forecasts(panel, certificates, predict, [.98, .005, .015])
        return result, seen

    def test_unfiled_fleet_and_future_cash_cannot_change_forecast(self):
        panel, certificates = self.fixtures()
        result, seen = self.evaluate(panel, certificates)
        changed = panel.copy()
        changed.loc[changed.period_end == pd.Timestamp("2026-01-31", tz="UTC"),
                    ["end_balance_cents", "first_default_event", "delinquency_days"]] = [1, 1, 999]
        different_cash = copy.deepcopy(certificates)
        for certificate in different_cash:
            if certificate["collection_period_end"] == "2026-02-28":
                certificate["amounts"]["defaults"] = "999999.00"
        altered, _ = self.evaluate(changed, different_cash)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(f.age_months.iloc[0] == 14 for f in seen))
        self.assertTrue(all(f.disclosure_lag_months.iloc[0] == 2 for f in seen))
        for first, second in zip(result["monthly"], altered["monthly"]):
            self.assertEqual(first["source_period"], "2025-12-31")
            self.assertEqual(first["bridge_months"], 2)
            for quantity in first["metrics"]:
                self.assertEqual(first["metrics"][quantity]["forecast_cents"],
                                 second["metrics"][quantity]["forecast_cents"])
            self.assertNotEqual(first["metrics"]["gross_defaults"]["observed_cents"],
                                second["metrics"]["gross_defaults"]["observed_cents"])

    def test_future_calibration_certificate_rejected(self):
        panel, certificates = self.fixtures()
        certificates[0]["acceptance_time"] = "2026-02-15T12:00:00Z"
        with self.assertRaisesRegex(ValueError, "not public"):
            self.evaluate(panel, certificates)


if __name__ == "__main__":
    unittest.main()
