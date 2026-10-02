import unittest
from credit_research.projections import competing_monthly, project_collateral, make_cohorts


class ProjectionTests(unittest.TestCase):
    def test_cause_specific_inverse_preserves_multinomial_rates(self):
        import math
        d, p = .01, .10
        hazard = -math.log1p(-d - p)
        annual_d = -math.expm1(-12 * hazard * d / (d + p))
        annual_p = -math.expm1(-12 * hazard * p / (d + p))
        result = competing_monthly(annual_d, annual_p)
        self.assertAlmostEqual(result[0], d, places=12)
        self.assertAlmostEqual(result[1], p, places=12)

    def test_matured_claim_not_given_new_median_term(self):
        import pandas as pd
        f = pd.DataFrame({"remaining_months": [0, 60], "interest_rate_pct": [8, 8], "end_balance_cents": [10000, 20000],
                          "previously_defaulted": [True, False]})
        cohorts, audit = make_cohorts(f, 30000)
        self.assertEqual(sum(c["balance_cents"] for c in cohorts), 30000)
        matured = next(c for c in cohorts if c["balance_cents"] == 10000)
        self.assertEqual(matured["remaining_months"], 1)
        self.assertEqual(matured["default_hazard_multiplier"], 2)
        self.assertEqual(audit["matured_positive_balance_loans"], 1)

    def test_competing_events_cannot_double_spend(self):
        d, p = competing_monthly(.95, .95)
        self.assertGreater(d, 0)
        self.assertLess(d + p, 1)

    def test_runoff_and_recovery_cash_conservation(self):
        periods, rows = project_collateral([dict(balance_cents=10000000, remaining_months=12, apr=.12)],
                                           "2026-09-15", annual_default_rate=.4, annual_prepayment_rate=.3,
                                           recovery_rate=.25, recovery_lag_months=3)
        self.assertEqual(rows[-1]["pool_end_cents"], 0)
        self.assertEqual(sum(r["default_cents"] + r["prepayment_cents"] + r["scheduled_principal_cents"] for r in rows), 10000000)
        # Flow rounding can differ by half a cent per default cohort month.
        self.assertAlmostEqual(sum(r["recovery_cents"] for r in rows), sum(r["default_cents"] for r in rows) * .25, delta=len(rows) / 2)
        self.assertTrue(all(r["pool_begin_cents"] - r["default_cents"] - r["prepayment_cents"] - r["scheduled_principal_cents"] == r["pool_end_cents"] for r in rows))

    def test_zero_hazards_amortize_contractually(self):
        _, rows = project_collateral([dict(balance_cents=1200, remaining_months=12, apr=0)], "2026-09-15",
                                    annual_default_rate=0, annual_prepayment_rate=0, recovery_rate=0, recovery_lag_months=1)
        self.assertEqual(len(rows), 12)
        self.assertEqual([r["scheduled_principal_cents"] for r in rows], [100] * 12)

    def test_nonclosed_horizon_rejected(self):
        with self.assertRaises(ValueError):
            project_collateral([dict(balance_cents=10000, remaining_months=60, apr=.1)], "2026-09-15",
                               annual_default_rate=0, annual_prepayment_rate=0, recovery_rate=0,
                               recovery_lag_months=1, horizon_months=10)

    def test_recovery_queues_not_repeated_cumulative(self):
        _, rows = project_collateral([dict(balance_cents=1000000, remaining_months=1, apr=0)], "2026-09-15",
                                    annual_default_rate=.8, annual_prepayment_rate=0, recovery_rate=.5, recovery_lag_months=2)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["recovery_cents"], 0)
        self.assertEqual(rows[2]["recovery_cents"], round(rows[0]["default_cents"] * .5))


if __name__ == "__main__":
    unittest.main()
