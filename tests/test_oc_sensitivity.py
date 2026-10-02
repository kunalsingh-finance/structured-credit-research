"""Independent valuation, unsupported-state and stale-input diagnostic controls."""
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.analyze_oc_sensitivity import (
    fixed_scenario_inputs, independent_value, reported_terms, validate_inputs,
)


class OCSensitivityControls(unittest.TestCase):
    def guard_fixture(self, status="SUCCESS", results_hash=None, certificate_hash=None):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "output").mkdir()
        (root / "data").mkdir()
        certificate_bytes = b'{"certificates": []}'
        (root / "data/actual_certificates.json").write_bytes(certificate_bytes)
        identity = {"certificate_sha256": certificate_hash or hashlib.sha256(certificate_bytes).hexdigest()}
        raw = json.dumps({"generated_at": "fixed", "build_identity": identity}).encode()
        (root / "output/platform_results.json").write_bytes(raw)
        control = {"status": status, "built_at": "fixed", "results_sha256": results_hash or hashlib.sha256(raw).hexdigest(), "identity": identity}
        (root / "output/platform_run_status.json").write_text(json.dumps(control), encoding="utf8")
        return temporary, root

    def test_building_primary_rejected_before_missing_inputs(self):
        temporary, root = self.guard_fixture(status="BUILDING")
        with temporary, self.assertRaisesRegex(ValueError, "not SUCCESS"):
            validate_inputs(root)

    def test_changed_primary_bytes_rejected(self):
        temporary, root = self.guard_fixture(results_hash="0" * 64)
        with temporary, self.assertRaisesRegex(ValueError, "results SHA mismatch"):
            validate_inputs(root)

    def test_changed_certificate_bytes_rejected(self):
        temporary, root = self.guard_fixture(certificate_hash="0" * 64)
        with temporary, self.assertRaisesRegex(ValueError, "Certificate SHA mismatch"):
            validate_inputs(root)

    def test_incomplete_corpus_is_not_an_accepted_bound(self):
        temporary, root = self.guard_fixture()
        with temporary, self.assertRaisesRegex(ValueError, "46-period"):
            validate_inputs(root)

    def test_hypothetical_dollar_target_preserves_other_terms(self):
        terms = reported_terms(141_057_942_174, 1_057_942_174)
        with localcontext() as ctx:
            ctx.prec = 80
            actual = Decimal(terms.initial_pool_balance) * Decimal(terms.oc_rate)
            self.assertLess(abs(actual - Decimal(1_057_942_174)), Decimal("0.0000000001"))
        self.assertEqual(terms.reserve_minimum, 352_644_855)
        self.assertEqual(terms.cleanup_threshold, "0.10")
        self.assertEqual(terms.servicing_rate, "0.01")

    def test_independent_value_excludes_terminal_loss(self):
        # A $100 principal payment plus $1 interest one day after origin;
        # $500 terminal impairment is a debt claim, never a cash receipt.
        tranche = {"rows": [{"distribution_date": "2026-01-02", "principal_paid_cents": 10_000,
                            "interest_paid_cents": 100, "loss_cents": 50_000}], "loss_cents": 50_000}
        pv, wal = independent_value(tranche, "2026-01-01", "0.08")
        with localcontext() as ctx:
            ctx.prec = 60
            expected = Decimal(10_100) / Decimal("1.08") ** (Decimal(1) / Decimal("365.25"))
            self.assertEqual(pv, expected)
            self.assertEqual(wal, Decimal(1) / Decimal("365.25"))
        tranche["rows"][0]["loss_cents"] = 500_000
        self.assertEqual(independent_value(tranche, "2026-01-01", "0.08"), (pv, wal))

    def test_unreviewed_elections_rejected(self):
        scenario = {"monthly": [{"accelerated": True, "cleanup_elected": False,
                                 "trustee_paid": 0, "senior_expenses_paid": 0}], "assumptions": {}}
        with self.assertRaisesRegex(ValueError, "does not support"):
            fixed_scenario_inputs(scenario, "2026-01-01")


if __name__ == "__main__":
    unittest.main()
