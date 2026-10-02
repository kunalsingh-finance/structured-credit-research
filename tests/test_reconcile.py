"""Independent arithmetic and schema examples for reported certificate checks."""

import copy
import unittest

from credit_research import CertificateError, parse_amount, reconcile, summarize


def balanced_certificate():
    """Synthetic rule fixture; not a contractual waterfall or actual deal record."""
    return {
        "deal_id": "SYNTHETIC-TEST", "collection_period_start": "2024-02-01",
        "collection_period_end": "2024-02-29", "distribution_date": "2024-03-15",
        "source_url": "https://example.org/synthetic-certificate.pdf",
        "extraction_method": "synthetic unit-test fixture",
        "amounts": {
            "pool_begin": "1000.00", "principal_collected": "100.00",
            "defaults": "20.00", "repurchases": "30.00", "pool_end": "850.00",
            "interest_collected": "10.00", "recoveries": "5.00", "investment_income": "2.00",
            "available_collections": "147.00", "servicing_fee": "2.00", "trustee_fee": "1.00",
            "total_note_interest": "10.00", "total_note_principal": "100.00",
            "reserve_deposit": "4.00", "residual_distribution": "33.00", "reserve_draw": "3.00",
            "total_distributions": "150.00", "note_begin": "500.00", "note_end": "400.00",
            "reserve_begin": "50.00", "reserve_interest": "1.00", "reserve_release": "2.00",
            "reserve_end": "50.00", "gross_loss": "20.00", "net_loss": "15.00",
        },
    }


class ArithmeticTests(unittest.TestCase):
    def test_all_seven_hand_calculated_identities_pass_exactly(self):
        rows = reconcile(balanced_certificate())
        self.assertEqual(len(rows), 7)
        self.assertEqual({row["status"] for row in rows}, {"PASS"})
        computed = {row["check_id"]: row["computed_cents"] for row in rows}
        self.assertEqual(computed, {
            "pool_rollforward": 85000, "collections_total": 14700,
            "collections_to_distributions": 15000, "distribution_components": 15000,
            "note_rollforward": 40000, "reserve_rollforward": 5000, "net_loss": 1500,
        })
        for row in rows:
            self.assertEqual(row["reported_cents"], row["computed_cents"])
            self.assertEqual(row["residual_cents"], 0)
            self.assertEqual(row["missing_fields"], [])
        self.assertEqual(summarize(rows), {"PASS": 7, "FAIL": 0, "SKIPPED": 0, "total": 7, "status": "PASS"})

    def test_one_cent_tampering_is_not_tolerated_or_repaired(self):
        certificate = balanced_certificate()
        certificate["amounts"]["pool_end"] = "850.01"
        original = copy.deepcopy(certificate)
        rows = reconcile(certificate)
        failed = [row for row in rows if row["status"] == "FAIL"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["check_id"], "pool_rollforward")
        self.assertEqual(failed[0]["computed_cents"], 85000)
        self.assertEqual(failed[0]["reported_cents"], 85001)
        self.assertEqual(failed[0]["residual_cents"], -1)
        self.assertEqual(summarize(rows)["status"], "FAIL")
        self.assertEqual(certificate, original)

    def test_residual_sign_is_computed_minus_reported(self):
        certificate = balanced_certificate()
        certificate["amounts"]["net_loss"] = "14.99"
        loss = next(row for row in reconcile(certificate) if row["check_id"] == "net_loss")
        self.assertEqual(loss["status"], "FAIL")
        self.assertEqual(loss["residual_cents"], 1)

    def test_missing_operands_skip_affected_checks_without_assuming_zero(self):
        certificate = balanced_certificate()
        del certificate["amounts"]["investment_income"]
        rows = reconcile(certificate)
        skipped = [row for row in rows if row["status"] == "SKIPPED"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["check_id"], "collections_total")
        self.assertEqual(skipped[0]["missing_fields"], ["investment_income"])
        for field in ("computed_cents", "reported_cents", "residual_cents"):
            self.assertIsNone(skipped[0][field])
        self.assertEqual(summarize(rows)["status"], "INCOMPLETE")

    def test_reserve_interest_and_release_are_required_even_when_source_could_be_zero(self):
        for missing in ("reserve_interest", "reserve_release"):
            certificate = balanced_certificate()
            del certificate["amounts"][missing]
            reserve = next(row for row in reconcile(certificate) if row["check_id"] == "reserve_rollforward")
            with self.subTest(missing=missing):
                self.assertEqual(reserve["status"], "SKIPPED")
                self.assertEqual(reserve["missing_fields"], [missing])
                self.assertIsNone(reserve["residual_cents"])

    def test_empty_amounts_skip_all_checks_and_empty_summary_is_incomplete(self):
        certificate = balanced_certificate()
        certificate["amounts"] = {}
        self.assertEqual(summarize(reconcile(certificate)), {"PASS": 0, "FAIL": 0, "SKIPPED": 7, "total": 7, "status": "INCOMPLETE"})
        self.assertEqual(summarize([]), {"PASS": 0, "FAIL": 0, "SKIPPED": 0, "total": 0, "status": "INCOMPLETE"})

    def test_all_zero_explicit_operands_pass(self):
        certificate = balanced_certificate()
        certificate["amounts"] = {field: "0.00" for field in certificate["amounts"]}
        self.assertEqual(summarize(reconcile(certificate))["PASS"], 7)

    def test_large_exact_amounts_do_not_round_in_a_decimal_context(self):
        certificate = balanced_certificate()
        certificate["amounts"]["pool_begin"] = "1000000000000000000000000000000.01"
        certificate["amounts"]["pool_end"] = "999999999999999999999999999850.01"
        pool = reconcile(certificate)[0]
        self.assertEqual(pool["status"], "PASS")
        self.assertEqual(pool["residual_cents"], 0)

    def test_summary_accepts_flattened_multi_certificate_checks_and_fail_dominates_skipped(self):
        partial = balanced_certificate()
        del partial["amounts"]["reserve_release"]
        failed = balanced_certificate()
        failed["amounts"]["pool_end"] = "0"
        summary = summarize(reconcile(partial) + reconcile(failed))
        self.assertEqual(summary, {"PASS": 12, "FAIL": 1, "SKIPPED": 1, "total": 14, "status": "FAIL"})

    def test_source_exceptions_are_not_changed_or_interpreted(self):
        certificate = balanced_certificate()
        certificate["source_exceptions"] = ["Rate row contains a year inconsistent with report date."]
        original = copy.deepcopy(certificate)
        self.assertEqual(summarize(reconcile(certificate))["PASS"], 7)
        self.assertEqual(certificate, original)


class SchemaTests(unittest.TestCase):
    def test_plain_decimal_strings_parse_exactly(self):
        self.assertEqual(parse_amount("0"), 0)
        self.assertEqual(parse_amount("12"), 1200)
        self.assertEqual(parse_amount("12.3"), 1230)
        self.assertEqual(parse_amount("12.30"), 1230)
        self.assertEqual(parse_amount("00012.30"), 1230)

    def test_unsupported_numeric_inputs_are_rejected(self):
        invalid = [True, False, 12, 12.3, None, "", "NaN", "Infinity", "-Infinity", "1e2",
                   "1E+2", "-1.00", "-0.00", "+1.00", "0.001", "1.000", " 1.00", "1.00 ",
                   "$1.00", "1,000.00", "1.", ".50", "١٢.٣٠"]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(CertificateError):
                parse_amount(value)

    def test_tiny_fractional_cent_cannot_be_silently_rounded(self):
        with self.assertRaises(CertificateError):
            parse_amount("1.0000000000000000000000000000000001")

    def test_supplied_null_and_unknown_amount_are_invalid_instead_of_skipped(self):
        for value in (None, False, 1.0):
            certificate = balanced_certificate()
            certificate["amounts"]["reserve_interest"] = value
            with self.subTest(value=value), self.assertRaises(CertificateError):
                reconcile(certificate)
        certificate = balanced_certificate()
        certificate["amounts"]["pool_balance_typo"] = "1.00"
        with self.assertRaises(CertificateError):
            reconcile(certificate)

    def test_dates_reject_wrong_format_invalid_days_and_wrong_order(self):
        changes = [
            {"collection_period_start": "20240201"},
            {"collection_period_start": "2024-2-01"},
            {"collection_period_end": "2024-02-30"},
            {"collection_period_start": "2024-03-01"},
            {"distribution_date": "2024-02-29"},
            {"distribution_date": "2024-02-28"},
            {"distribution_date": True},
            {"distribution_date": "0000-03-15"},
        ]
        for change in changes:
            certificate = balanced_certificate()
            certificate.update(change)
            with self.subTest(change=change), self.assertRaises(CertificateError):
                reconcile(certificate)

    def test_collection_period_must_be_a_full_calendar_month(self):
        changes = [
            {"collection_period_start": "2024-02-02"},
            {"collection_period_end": "2024-02-28"},
            {"collection_period_end": "2024-03-01"},
            {"collection_period_start": "2024-01-15", "collection_period_end": "2024-02-14"},
        ]
        for change in changes:
            certificate = balanced_certificate()
            certificate.update(change)
            with self.subTest(change=change), self.assertRaises(CertificateError):
                reconcile(certificate)

    def test_month_length_validation_supports_nonleap_and_year_end(self):
        for start, end, distribution in (
            ("2025-02-01", "2025-02-28", "2025-03-17"),
            ("2025-12-01", "2025-12-31", "2026-01-15"),
            ("2025-04-01", "2025-04-30", "2025-05-15"),
        ):
            certificate = balanced_certificate()
            certificate.update(collection_period_start=start, collection_period_end=end, distribution_date=distribution)
            with self.subTest(start=start):
                self.assertEqual(summarize(reconcile(certificate))["PASS"], 7)

    def test_missing_metadata_and_nonobject_inputs_reject(self):
        for missing in ("deal_id", "collection_period_start", "collection_period_end", "distribution_date", "source_url", "extraction_method"):
            certificate = balanced_certificate()
            del certificate[missing]
            with self.subTest(missing=missing), self.assertRaises(CertificateError):
                reconcile(certificate)
        for value in (None, [], "certificate"):
            with self.subTest(value=value), self.assertRaises(CertificateError):
                reconcile(value)
        for value in (None, [], "amounts"):
            certificate = balanced_certificate()
            certificate["amounts"] = value
            with self.subTest(amounts=value), self.assertRaises(CertificateError):
                reconcile(certificate)

    def test_unknown_summary_status_is_not_silently_ignored(self):
        for rows in ([{"status": "passed"}], [{"status": []}], [{}], [None], None):
            with self.subTest(rows=rows), self.assertRaises(CertificateError):
                summarize(rows)


if __name__ == "__main__":
    unittest.main()
