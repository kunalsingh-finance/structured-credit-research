"""Hand-calculated state, cash, priority and economic-closure controls."""

from dataclasses import replace
from decimal import Decimal
import unittest

from credit_research.cashflows import (CollateralPeriod, DealTerms, ScenarioState,
                                       distribute_period, reverse_stress, run_scenario)
from credit_research.waterfall import NOTES, replay
from test_waterfall import august_case


def balances(**values):
    return {n: values.get(n, 0) for n in NOTES}


def zero_terms(**changes):
    return DealTerms(initial_pool_balance=100_000, reserve_minimum=0, oc_rate="0",
                     servicing_rate="0", fixed_rates={n: "0" for n in NOTES if n != "A2b"},
                     **changes)


def period(**changes):
    return CollateralPeriod(distribution_date="2025-09-15", pool_end=100_000,
                            principal_collected=0, interest_collected=0,
                            floating_note_rate="0", **changes)


class CashFlowTests(unittest.TestCase):
    def test_fully_funded_case_matches_independent_existing_replay(self):
        case = august_case()
        cents = lambda v: int(Decimal(v) * 100)
        state = ScenarioState(cents(case["pool_begin"]), {n: cents(v) for n, v in case["note_begin"].items()},
                              cents(case["reserve_begin"]), case["prior_distribution_date"])
        # Collection decomposition comes from certificate source inputs.
        p = CollateralPeriod(case["distribution_date"], cents(case["pool_end"]),
                             4_392_326_486, 973_795_169, recoveries=28_115_954,
                             defaults=105_829_304, investment_income=17_354_007,
                             reserve_interest=1_260_152, floating_note_rate=case["floating_note_rate"])
        _, row = distribute_period(state, p)
        independent = replay(case)
        for n in ("interest", "principal", "note_end", "reserve_release", "reserve_end", "residual_distribution"):
            self.assertEqual(row[n], independent[n], n)
        self.assertEqual(row["oc_target"], independent["contractual_oc_target"])
        self.assertTrue(all(row["checks"][n] for n in ("cash_conservation", "pool_conservation", "principal_conservation")))

    def test_default_without_cash_draws_reserve_and_preserves_debt(self):
        terms = replace(zero_terms(), reserve_minimum=5_000)
        state = ScenarioState(100_000, balances(A1=100_000), 5_000, "2025-08-15")
        p = replace(period(), pool_end=99_000, defaults=1_000)
        end, row = distribute_period(state, p, terms)
        self.assertEqual(row["reserve_draw"], 1_000)
        self.assertEqual(row["principal"]["A1"], 1_000)
        self.assertEqual(end.reserve_balance, 4_000)
        self.assertEqual(end.note_balances["A1"], 99_000)
        self.assertEqual(row["reserve_deposit"], 0)

    def test_scenario_reserve_draw_replenishment_and_final_release_conserve_cash(self):
        terms = replace(zero_terms(), reserve_minimum=5_000)
        state = ScenarioState(100_000, balances(A1=100_000), 5_000, "2025-08-15")
        periods = [
            replace(period(), pool_end=99_000, defaults=1_000),
            replace(period(), distribution_date="2025-10-15", pool_end=99_000,
                    interest_collected=1_000),
            replace(period(), distribution_date="2025-11-17", pool_end=0,
                    principal_collected=99_000),
        ]
        result = run_scenario(state, periods, terms)
        first, second, last = result["monthly"]
        self.assertEqual(first["reserve_draw"], 1_000)
        self.assertEqual(first["reserve_end"], 4_000)
        self.assertEqual(second["reserve_deposit"], 1_000)
        self.assertEqual(second["reserve_end"], 5_000)
        self.assertEqual(last["reserve_release"], 5_000)
        self.assertEqual(result["final_state"]["reserve_balance"], 0)
        self.assertEqual(result["tranches"][0]["principal_paid_cents"], 100_000)
        self.assertTrue(result["checks"]["reserve_conservation"])
        self.assertTrue(result["checks"]["cash_conservation"])
        self.assertTrue(result["checks"]["horizon_closed"])

    def test_reserve_does_not_pay_affiliated_servicing_and_formula_reduction_is_explicit(self):
        terms = replace(zero_terms(), reserve_minimum=1_000, servicing_rate="0.012")
        state = ScenarioState(100_000, balances(A1=100_000), 1_000, "2025-08-15")
        end, row = distribute_period(state, replace(period(), pool_end=99_000, defaults=1_000), terms)
        # Required 1,100; min(shortfall, reserve)=1,000 less affiliate fee100.
        self.assertEqual(row["servicing_due"], 100)
        self.assertEqual(row["reserve_draw"], 900)
        self.assertEqual(row["servicing_paid"], 0)
        self.assertEqual(end.servicing_arrears, 100)
        self.assertEqual(row["principal"]["A1"], 900)
        self.assertEqual(row["checks"]["affiliate_servicing_reserve_cents"], 0)

    def test_class_a_interest_shortage_is_pro_rata(self):
        terms = zero_terms()
        terms = replace(terms, fixed_rates={**terms.fixed_rates, "A1": "0.12", "A2a": "0.12"})
        state = ScenarioState(100_000, balances(A1=10_000, A2a=10_000), 0, "2025-08-15")
        _, row = distribute_period(state, replace(period(), interest_collected=50), terms)
        # Actual/360 A1=103, monthly30/360 A2a=100; largest-remainder cents.
        self.assertEqual(row["interest_due"]["A1"], 103)
        self.assertEqual(row["interest"]["A1"], 25)
        self.assertEqual(row["interest"]["A2a"], 25)
        self.assertEqual(row["interest_shortfalls"]["A1"], 78)
        self.assertEqual(row["interest_shortfalls"]["A2a"], 75)

    def test_interest_arrears_charge_unpaid_monthly_interest_without_compounding_charges(self):
        terms = zero_terms()
        terms = replace(terms, fixed_rates={**terms.fixed_rates, "A2a": "0.12"})
        state = ScenarioState(100_000, balances(A2a=10_000), 0, "2025-08-15")
        state, first = distribute_period(state, period(), terms)
        state, second = distribute_period(state, replace(period(), distribution_date="2025-10-15"), terms)
        state, third = distribute_period(state, replace(period(), distribution_date="2025-11-17"), terms)
        self.assertEqual(first["interest_shortfalls"]["A2a"], 100)
        self.assertEqual(second["interest_on_arrears"]["A2a"], 1)
        self.assertEqual(third["interest_on_arrears"]["A2a"], 2)
        self.assertEqual(state.interest_arrears["A2a"], 300)
        self.assertEqual(state.overdue_interest_arrears["A2a"], 3)
        self.assertEqual(third["interest_shortfalls"]["A2a"], 303)

    def test_a1_maturity_floor_reports_failure_and_can_draw_reserve(self):
        terms = replace(zero_terms(), reserve_minimum=5_000)
        state = ScenarioState(100_000, balances(A1=10_000), 5_000, "2026-04-15")
        end, row = distribute_period(state, replace(period(), distribution_date="2026-05-15"), terms)
        self.assertEqual(row["principal_tier_due"]["priority"], 10_000)
        self.assertEqual(row["principal"]["A1"], 5_000)
        self.assertEqual(row["maturity_shortfalls"]["A1"], 5_000)
        self.assertEqual(end.note_balances["A1"], 5_000)

    def test_sequential_principal_and_a2_pro_rata_are_exact(self):
        terms = zero_terms()
        state = ScenarioState(100_000, balances(A1=100, A2a=300, A2b=100, A3=500), 0, "2025-08-15")
        _, row = distribute_period(state, replace(period(), pool_end=99_600, principal_collected=400), terms)
        # OC0 and notes1000 < pool => no principal due; set maturity floor A2.
        terms = replace(terms, final_dates={**terms.final_dates, "A1": "2025-09-15", "A2a": "2025-09-15", "A2b": "2025-09-15"})
        _, row = distribute_period(state, replace(period(), pool_end=99_600, principal_collected=400), terms)
        self.assertEqual(row["principal"]["A1"], 100)
        self.assertEqual(row["principal"]["A2a"], 225)
        self.assertEqual(row["principal"]["A2b"], 75)
        self.assertEqual(row["principal"]["A3"], 0)

    def test_payoff_sweep_uses_reserve_and_skips_topup_with_remaining_collateral(self):
        terms = replace(zero_terms(), reserve_minimum=3_000)
        state = ScenarioState(100_000, balances(A2a=2_000), 3_000, "2025-08-15")
        end, row = distribute_period(state, period(), terms)
        self.assertTrue(row["payoff_sweep"])
        self.assertEqual(row["principal"]["A2a"], 2_000)
        self.assertEqual(row["reserve_deposit"], 0)
        self.assertEqual(row["reserve_release"], 1_000)
        self.assertEqual(end.note_balances["A2a"], 0)
        self.assertEqual(end.pool_balance, 100_000)

    def test_a2_ratability_is_independent_of_principal_tier_partition(self):
        # A2 opening shares7:3 and total payment2 cents imply1:1 after
        # rounding the total once. Two separately rounded1-cent payments
        # would incorrectly send both cents to A2a.
        allocations = []
        for junior_balance, pool_end in ((0, 8), (1, 9)):
            with self.subTest(junior_balance=junior_balance):
                state = ScenarioState(100_000, balances(A2a=7, A2b=3, B=junior_balance), 0, "2025-08-15")
                end, row = distribute_period(state, replace(period(), pool_end=pool_end,
                    defaults=100_000-pool_end, interest_collected=2), zero_terms())
                allocations.append(row["principal"])
                self.assertEqual(row["principal"]["A2a"], 1)
                self.assertEqual(row["principal"]["A2b"], 1)
                self.assertEqual(end.note_balances["A2a"], 6)
                self.assertEqual(end.note_balances["A2b"], 2)
                self.assertTrue(row["checks"]["cash_conservation"])
        self.assertEqual(allocations[0], allocations[1])

    def test_reserve_extra_regular_principal_uses_same_monthly_a2_ratio(self):
        terms = replace(zero_terms(), oc_rate="0.00002")
        state = ScenarioState(100_000, balances(A2a=7, A2b=3), 1, "2025-08-15")
        _, row = distribute_period(state, replace(period(), pool_end=10,
            defaults=99_990, interest_collected=1), terms)
        self.assertEqual(row["principal_tier_paid"]["regular"], 2)
        self.assertEqual(row["reserve_excess_principal"], 1)
        self.assertEqual(row["principal"]["A2a"], 1)
        self.assertEqual(row["principal"]["A2b"], 1)
        self.assertTrue(row["checks"]["reserve_conservation"])

    def test_split_tiers_cannot_overpay_a_small_a2_class(self):
        state = ScenarioState(100_000, balances(A2a=1, A2b=1, B=1), 0, "2025-08-15")
        end, row = distribute_period(state, replace(period(), pool_end=1,
            defaults=99_999, interest_collected=2), zero_terms())
        self.assertEqual(row["principal"], balances(A2a=1, A2b=1))
        self.assertEqual(end.note_balances["A2a"], 0)
        self.assertEqual(end.note_balances["A2b"], 0)
        self.assertTrue(row["checks"]["principal_conservation"])

    def test_acceleration_payment_default_blocks_junior_interest_behind_senior_principal(self):
        terms = zero_terms()
        terms = replace(terms, fixed_rates={**terms.fixed_rates, "B": "0.12"})
        state = ScenarioState(100_000, balances(A1=500, B=10_000), 0, "2025-08-15")
        _, row = distribute_period(state, replace(period(), interest_collected=500,
                          accelerated=True, acceleration_reason="payment_or_bankruptcy"), terms)
        self.assertEqual(row["principal"]["A1"], 500)
        self.assertEqual(row["interest"]["B"], 0)
        self.assertEqual(row["interest_shortfalls"]["B"], 100)

    def test_acceleration_covenant_default_pays_junior_interest_before_principal(self):
        terms = zero_terms()
        terms = replace(terms, fixed_rates={**terms.fixed_rates, "B": "0.12"})
        state = ScenarioState(100_000, balances(A1=500, B=10_000), 0, "2025-08-15")
        _, row = distribute_period(state, replace(period(), interest_collected=500,
                          accelerated=True, acceleration_reason="covenant_or_representation"), terms)
        self.assertEqual(row["interest"]["B"], 100)
        self.assertEqual(row["principal"]["A1"], 400)

    def test_accelerated_remaining_class_a_principal_is_pro_rata_not_sequential(self):
        state = ScenarioState(100_000, balances(A1=100, A2a=150, A2b=50, A3=200, A4=400), 0, "2025-08-15")
        end, row = distribute_period(state, replace(period(), interest_collected=500,
                               accelerated=True, acceleration_reason="payment_or_bankruptcy"), zero_terms())
        self.assertEqual(row["principal"], balances(A1=100, A2a=75, A2b=25, A3=100, A4=200))
        self.assertTrue(end.accelerated)
        self.assertEqual(end.acceleration_reason, "payment_or_bankruptcy")

    def test_accelerated_second_tier_expenses_share_a_shortage_pro_rata(self):
        state = ScenarioState(100_000, balances(A1=1_000), 0, "2025-08-15")
        end, row = distribute_period(state, replace(period(), interest_collected=100,
                               senior_expenses=100, trustee_fee=100,
                               accelerated=True, acceleration_reason="payment_or_bankruptcy"), zero_terms())
        self.assertEqual(row["senior_expenses_paid"], 50)
        self.assertEqual(row["trustee_paid"], 50)
        self.assertEqual(end.senior_expense_arrears, 50)
        self.assertEqual(end.trustee_arrears, 50)
        self.assertEqual(row["principal"]["A1"], 0)

    def test_accelerated_reserve_residual_requires_separate_trust_termination(self):
        state = ScenarioState(100_000, balances(A1=10_000), 3_000, "2025-08-15")
        p = replace(period(), pool_end=0, principal_collected=100_000,
                    accelerated=True, acceleration_reason="payment_or_bankruptcy")
        end, row = distribute_period(state, p, zero_terms())
        self.assertEqual(row["reserve_release"], 0)
        self.assertEqual(row["residual_distribution"], 90_000)
        self.assertEqual(end.reserve_balance, 3_000)
        self.assertTrue(row["checks"]["reserve_conservation"])
        end, row = distribute_period(state, replace(p, trust_termination=True), zero_terms())
        self.assertEqual(row["reserve_termination_release"], 3_000)
        self.assertEqual(end.reserve_balance, 0)
        self.assertTrue(row["checks"]["cash_conservation"])
        self.assertTrue(row["checks"]["reserve_conservation"])

    def test_cleanup_requires_threshold_price_notice_and_complete_redemption(self):
        state = ScenarioState(20_000, balances(A1=10_000), 0, "2025-08-15")
        p = replace(period(), pool_end=10_000, principal_collected=10_000,
                    cleanup_elected=True, cleanup_price=10_000, cleanup_notice_days=10)
        end, row = distribute_period(state, p, zero_terms())
        self.assertEqual(end.pool_balance, 0)
        self.assertEqual(row["principal"]["A1"], 10_000)
        self.assertEqual(row["residual_distribution"], 10_000)
        self.assertTrue(row["checks"]["cash_conservation"])
        for change in ({"cleanup_notice_days": 9}, {"cleanup_price": 9_999},
                       {"cleanup_accrued_receivable_interest": 1},
                       {"pool_end": 10_001, "principal_collected": 9_999}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                distribute_period(state, replace(p, **change), zero_terms())

    def test_terminal_loss_is_not_principal_cash_and_paid_wal_is_separate(self):
        state = ScenarioState(100_000, balances(A1=100_000), 0, "2025-08-15")
        p = replace(period(), pool_end=0, principal_collected=25_000, defaults=75_000)
        result = run_scenario(state, [p], zero_terms())
        a = result["tranches"][0]
        self.assertEqual(a["principal_paid_cents"], 25_000)
        self.assertEqual(a["loss_cents"], 75_000)
        self.assertIsNone(a["wal_years"])
        self.assertAlmostEqual(a["repaid_principal_wal_years"], 31/365.25)
        self.assertEqual(a["principal_recovery_fraction"], .25)
        self.assertEqual(a["contractual_remaining_balance_cents"], 75_000)
        self.assertTrue(result["checks"]["horizon_closed"])
        self.assertEqual(a["opening_balance_cents"], a["principal_paid_cents"] + a["loss_cents"])

    def test_live_collateral_or_undeclared_recoveries_cannot_be_written_off(self):
        state = ScenarioState(100_000, balances(A1=100_000), 0, "2025-08-15")
        p = replace(period(), pool_end=50_000, defaults=50_000)
        result = run_scenario(state, [p], zero_terms())
        self.assertFalse(result["checks"]["horizon_closed"])
        self.assertEqual(result["tranches"][0]["loss_cents"], 0)
        p = replace(period(), pool_end=0, defaults=100_000)
        result = run_scenario(state, [p], zero_terms(), terminal=False)
        self.assertFalse(result["checks"]["horizon_closed"])
        self.assertEqual(result["tranches"][0]["loss_cents"], 0)

    def test_input_controls_reject_float_boolean_pool_break_and_election_without_reason(self):
        with self.assertRaises(ValueError):
            ScenarioState(100_000.0, balances(A1=100), 0, "2025-08-15")
        with self.assertRaises(ValueError):
            replace(period(), defaults=True)
        with self.assertRaises(ValueError):
            replace(period(), accelerated=True)
        state = ScenarioState(100_000, balances(A1=100), 0, "2025-08-15")
        with self.assertRaises(ValueError):
            distribute_period(state, replace(period(), pool_end=99_999), zero_terms())
        early = ScenarioState(100_000, balances(A1=100), 0, "2025-05-02")
        with self.assertRaisesRegex(ValueError, "stub"):
            distribute_period(early, replace(period(), distribution_date="2025-06-15"), zero_terms())

    def test_reverse_stress_evaluates_entire_nonmonotonic_grid_and_no_breach_at_zero(self):
        def factory(severity):
            state = ScenarioState(100_000, balances(D=100_000), 0, "2025-08-15")
            loss = 1_000 if severity == Decimal("1") else 0
            p = replace(period(), pool_end=0, principal_collected=100_000-loss, defaults=loss)
            return run_scenario(state, [p], zero_terms())
        result = reverse_stress(factory, ["0", "1", "2"], tranche="D")
        self.assertEqual(result["first_breach"]["severity"], "1")
        self.assertEqual(result["preceding_safe"]["severity"], "0")
        self.assertFalse(result["grid"][2]["breach"])
        self.assertEqual(len(result["grid"]), 3)
        at_zero = reverse_stress(factory, ["1", "2"], tranche="D")
        self.assertIsNone(at_zero["preceding_safe"])
        with self.assertRaisesRegex(ValueError, "increase strictly"):
            reverse_stress(factory, ["2", "1"], tranche="D")


if __name__ == "__main__":
    unittest.main()
