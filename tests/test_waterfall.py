"""Independent example checks and scope controls for the bounded replay."""

from copy import deepcopy
import unittest

from credit_research.waterfall import NOTES, UnsupportedReplay, replay


def august_case():
    # Observed August-2025 collateral and beginning balances; no expected outputs.
    return {
        "pool_begin": "1221045205.24",
        "pool_end": "1176063647.34",
        "available_collections": "54115916.16",
        "reserve_begin": "3526448.55",
        "reserve_interest": "12601.52",
        "prior_distribution_date": "2025-08-15",
        "distribution_date": "2025-09-15",
        "floating_note_rate": "0.0503270",
        "note_begin": {
            "A1": "93665783.50", "A2a": "350000000.00", "A2b": "161510000.00",
            "A3": "452100000.00", "A4": "89000000.00", "B": "28920000.00",
            "C": "21160000.00", "D": "14110000.00",
        },
    }


class WaterfallReplayTests(unittest.TestCase):
    def test_observed_interest_and_contractual_oc_are_independent_checks(self):
        result = replay(august_case())
        self.assertEqual(result["act_360_days"], 31)
        self.assertEqual(result["servicing_fee"], 101_753_767)
        self.assertEqual(result["interest"], {
            "A1": 36_037_390, "A2a": 133_875_000, "A2b": 69_993_813,
            "A3": 168_784_000, "A4": 34_487_500, "B": 11_953_600,
            "C": 9_098_800, "D": 6_749_283,
        })
        self.assertEqual(result["contractual_oc_target"], 1_057_934_566)
        # The certificate reports $10,579,421.74. Keep its $76.08 discrepancy.
        self.assertEqual(1_057_942_174 - result["contractual_oc_target"], 7_608)
        self.assertEqual(result["priority"], 0)
        self.assertEqual(result["secondary"], 0)
        self.assertEqual(result["tertiary"], 2_029_213_616)
        self.assertEqual(result["quaternary"], 1_411_000_000)
        self.assertEqual(result["regular"], 1_057_934_566)
        self.assertEqual(result["total_note_principal"], 4_498_148_182)
        self.assertEqual(result["principal"]["A1"], 4_498_148_182)
        self.assertEqual(result["note_end"]["A1"], 4_868_430_168)
        self.assertEqual(result["residual_distribution"], 340_710_281)
        self.assertEqual(result["reserve_release"], 1_260_152)
        self.assertEqual(result["reserve_end"], 352_644_855)

    def test_cash_and_debt_conservation(self):
        result = replay(august_case())
        self.assertEqual(
            5_411_591_616,
            result["servicing_fee"] + result["total_note_interest"]
            + result["total_note_principal"] + result["reserve_deposit"]
            + result["residual_distribution"],
        )
        self.assertEqual(
            352_644_855 + 1_260_152 + result["reserve_deposit"],
            result["reserve_end"] + result["reserve_release"],
        )
        self.assertEqual(121_046_578_350, result["total_note_principal"] + sum(result["note_end"].values()))
        self.assertEqual(sum(result["interest"].values()), result["total_note_interest"])
        self.assertEqual(sum(result["principal"].values()), result["total_note_principal"])
        self.assertTrue(all(value >= 0 for value in result["note_end"].values()))

    def test_expected_outputs_are_not_read_and_inputs_are_not_mutated(self):
        case = august_case()
        original = deepcopy(case)
        baseline = replay(case)
        case["expected"] = {"principal": {"A1": "0.00"}, "oc_target": "0.00"}
        case["reported_target"] = "10579421.74"
        self.assertEqual(replay(case), baseline)
        self.assertEqual({key: case[key] for key in original}, original)

    def test_a2_group_is_pro_rata_after_a1_is_paid(self):
        case = august_case()
        case["pool_end"] = "1100000000.00"
        case["available_collections"] = "200000000.00"
        result = replay(case)
        self.assertEqual(result["principal"]["A1"], 9_366_578_350)
        self.assertEqual(result["principal"]["A2a"] + result["principal"]["A2b"], 2_737_934_566)
        self.assertEqual(result["note_end"]["A1"], 0)
        self.assertEqual(result["principal"]["A3"], 0)
        # Verify proportionality without recalculating the implementation's rounding.
        cross_product_error = abs(result["principal"]["A2a"] * 51_151_000_000 - 2_737_934_566 * 35_000_000_000)
        self.assertLessEqual(cross_product_error, 51_151_000_000 // 2)
        self.assertEqual(sum(result["principal"].values()), result["total_note_principal"])

    def test_a2_half_cent_goes_to_a2a_and_remainder_is_exact(self):
        case = august_case()
        case["pool_begin"] = "10579347.66"
        case["pool_end"] = "10579347.65"
        case["available_collections"] = "1000000.00"
        case["note_begin"] = dict.fromkeys(NOTES, "0.00")
        case["note_begin"].update({"A2a": "1.00", "A2b": "1.00"})
        result = replay(case)
        self.assertEqual(result["total_note_principal"], 1)
        self.assertEqual(result["principal"]["A2a"], 1)
        self.assertEqual(result["principal"]["A2b"], 0)

    def test_principal_cannot_exceed_notes(self):
        case = august_case()
        case["pool_end"] = "1.00"
        case["available_collections"] = "1500000000.00"
        result = replay(case)
        self.assertEqual(result["total_note_principal"], 121_046_578_350)
        self.assertEqual(sum(result["note_end"].values()), 0)
        self.assertEqual(result["regular"], 100)

    def test_reserve_top_up_is_a_collection_cash_use(self):
        case = august_case()
        case["reserve_begin"] = "3526300.00"
        case["reserve_interest"] = "0.00"
        result = replay(case)
        self.assertEqual(result["reserve_deposit"], 14_855)
        self.assertEqual(result["reserve_end"], 352_644_855)
        self.assertEqual(result["reserve_release"], 0)
        self.assertEqual(result["residual_distribution"], 340_695_426)

    def test_underfunding_rejects_even_with_large_reserve(self):
        case = august_case()
        case["available_collections"] = "1000000.00"
        case["reserve_begin"] = "100000000.00"
        with self.assertRaisesRegex(UnsupportedReplay, "insufficient collection cash"):
            replay(case)

    def test_underfunding_at_regular_principal_is_not_partial_success(self):
        case = august_case()
        case["available_collections"] = "45000000.00"
        with self.assertRaisesRegex(UnsupportedReplay, "regular principal"):
            replay(case)

    def test_input_and_scope_rejection(self):
        changes = [
            ("pool_begin", "0.00"), ("pool_end", "0.00"), ("pool_end", "1221045205.25"),
            ("available_collections", "-1.00"), ("available_collections", "1.001"),
            ("available_collections", 54_115_916.16), ("available_collections", "NaN"),
            ("floating_note_rate", "-0.01"), ("floating_note_rate", "Infinity"),
            ("distribution_date", "2026-05-15"), ("distribution_date", "2025-08-15"),
            ("distribution_date", "2025-10-15"), ("distribution_date", "2025-09-31"),
            ("distribution_date", "20250915"), ("prior_distribution_date", "2025-05-02"),
            ("accelerated", True), ("cleanup_call", True), ("shortfalls", True),
            ("arrears", "0.01"), ("repurchase_fees", "1.00"), ("reserve_draw", "0.01"),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                case = august_case()
                case[key] = value
                with self.assertRaises(UnsupportedReplay):
                    replay(case)

    def test_note_keys_and_values_are_controlled(self):
        for alteration in ("missing", "extra", "negative", "all_zero"):
            with self.subTest(alteration=alteration):
                case = august_case()
                if alteration == "missing":
                    del case["note_begin"]["D"]
                elif alteration == "extra":
                    case["note_begin"]["E"] = "0.00"
                elif alteration == "negative":
                    case["note_begin"]["A1"] = "-1.00"
                else:
                    case["note_begin"] = dict.fromkeys(NOTES, "0.00")
                with self.assertRaises(UnsupportedReplay):
                    replay(case)

    def test_missing_required_input_rejects(self):
        case = august_case()
        del case["reserve_interest"]
        with self.assertRaisesRegex(UnsupportedReplay, "reserve_interest"):
            replay(case)


if __name__ == "__main__":
    unittest.main()
