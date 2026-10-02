"""Integration checks for source evidence, unsupported scope and failed rebuilds."""

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("research_runner", ROOT / "scripts" / "run_research.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ResearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / "data" / "certificates.json").read_text(encoding="utf-8"))

    def test_real_cases_arithmetic_and_preserved_oc_difference(self):
        pack = runner.build(self.fixture)
        self.assertEqual(pack["arithmetic_summary"], {"PASS": 14, "FAIL": 0, "SKIPPED": 0, "total": 14, "status": "PASS"})
        self.assertEqual(pack["replay_difference_count"], 14)
        self.assertEqual(pack["status"], "REVIEW REQUIRED")
        for record in pack["certificates"]:
            results = {row["name"]: row for row in record["replay_comparison"]}
            self.assertEqual(results["oc_target"]["residual_cents"], -7608)
            self.assertEqual(results["total_note_principal"]["residual_cents"], -7608)
            self.assertEqual(results["residual_distribution"]["residual_cents"], 7608)
            self.assertEqual(len(results), 37)
            self.assertTrue(all(results[f"interest.{note}"]["status"] == "PASS" for note in runner.NOTES))
        self.assertIsNone(pack["original_source_hashes"])

    def test_every_unsupported_scope_condition_rejects(self):
        for name in runner.ZERO_ASSUMPTIONS + runner.FALSE_ASSUMPTIONS:
            fixture = copy.deepcopy(self.fixture)
            fixture["scope_assumptions"][name] = "100.00" if name in runner.ZERO_ASSUMPTIONS else True
            with self.subTest(condition=name), self.assertRaises(ValueError):
                runner.build(fixture)
        fixture = copy.deepcopy(self.fixture)
        fixture["scope_assumptions"].pop("other_fees")
        with self.assertRaises(ValueError):
            runner.build(fixture)

    def test_nonzero_certificate_draw_or_fee_rejects(self):
        for name in ("reserve_draw", "trustee_fee"):
            fixture = copy.deepcopy(self.fixture)
            fixture["certificates"][0]["amounts"][name] = "1.00"
            with self.subTest(field=name), self.assertRaises(ValueError):
                runner.build(fixture)

    def test_contradictory_replay_scope_cannot_be_overwritten(self):
        for name, value in (("accelerated", True), ("cleanup_call", True), ("additional_fees", "100.00"),
                            ("interest_arrears", "100.00"), ("reserve_draw", "100.00"),
                            ("unreimbursed_servicer_advances", "100.00")):
            fixture = copy.deepcopy(self.fixture)
            fixture["certificates"][0]["replay_inputs"][name] = value
            with self.subTest(condition=name), self.assertRaises(ValueError):
                runner.build(fixture)

    def test_other_deal_and_misaligned_collection_period_reject(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["certificates"][0]["deal_id"] = "OTHER-TRUST"
        with self.assertRaises(ValueError):
            runner.build(fixture)
        fixture = copy.deepcopy(self.fixture)
        fixture["certificates"][0]["collection_period_start"] = "2025-07-01"
        fixture["certificates"][0]["collection_period_end"] = "2025-07-31"
        with self.assertRaises(ValueError):
            runner.build(fixture)

    def test_missing_note_comparisons_are_not_silently_omitted(self):
        for group in ("interest", "principal", "note_end"):
            fixture = copy.deepcopy(self.fixture)
            fixture["certificates"][0]["expected"][group] = {}
            with self.subTest(group=group), self.assertRaises(ValueError):
                runner.build(fixture)

    def test_one_cent_mismatch_in_note_beginning_or_expected_rejects(self):
        for group in ("note_begin", "interest", "principal", "note_end"):
            fixture = copy.deepcopy(self.fixture)
            cert = fixture["certificates"][0]
            target = cert["replay_inputs"][group] if group == "note_begin" else cert["expected"][group]
            cents = runner.parse_amount(target["A1"]) + 1
            target["A1"] = f"{cents // 100}.{cents % 100:02d}"
            with self.subTest(group=group), self.assertRaises(ValueError):
                runner.build(fixture)

    def test_duplicate_period_rejects_and_expected_does_not_mutate_fixture(self):
        before = copy.deepcopy(self.fixture)
        runner.build(self.fixture)
        self.assertEqual(self.fixture, before)
        self.fixture["certificates"].append(copy.deepcopy(self.fixture["certificates"][0]))
        with self.assertRaises(ValueError):
            runner.build(self.fixture)

    def test_render_discloses_limits_and_keeps_all_comparisons(self):
        pack = runner.build(self.fixture)
        pack["normalized_fixture_sha256"] = "abc123"
        output = runner.render(pack)
        self.assertIn("REVIEW REQUIRED", output)
        self.assertIn("$76.08", output)
        self.assertIn("original source bytes and source hashes unavailable", output)
        self.assertIn("neither withheld-month mechanical validation nor forecast backtesting", output)
        self.assertEqual(output.count('<tr class="difference">'), 14)
        self.assertEqual(output.count("<article>"), 2)

    def test_failed_rebuild_invalidates_old_machine_evidence(self):
        with tempfile.TemporaryDirectory(prefix="structured_credit_test_") as directory:
            temporary_root = Path(directory)
            (temporary_root / "data").mkdir()
            (temporary_root / "output").mkdir()
            (temporary_root / "data" / "certificates.json").write_text("invalid json", encoding="utf-8")
            for name in ("research_results.json", "research_report.html", "replay_comparison.csv", "reconciliation_checks.csv"):
                (temporary_root / "output" / name).write_text("STALE_RESULT", encoding="utf-8")
            with patch.object(runner, "ROOT", temporary_root), patch.object(sys, "argv", ["run_research.py"]), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            output = temporary_root / "output"
            results = json.loads((output / "research_results.json").read_text(encoding="utf-8"))
            self.assertEqual(results["status"], "ERROR")
            self.assertEqual(results["certificates"], [])
            self.assertEqual(json.loads((output / "run_status.json").read_text())["status"], "ERROR")
            for name in ("research_results.json", "research_report.html", "replay_comparison.csv", "reconciliation_checks.csv"):
                self.assertNotIn("STALE_RESULT", (output / name).read_text(encoding="utf-8"))

    def test_strict_gate_returns_two_for_unresolved_difference(self):
        with tempfile.TemporaryDirectory(prefix="structured_credit_test_") as directory:
            temporary_root = Path(directory)
            (temporary_root / "data").mkdir()
            (temporary_root / "configs").mkdir()
            (temporary_root / "data" / "certificates.json").write_text(json.dumps(self.fixture), encoding="utf-8")
            (temporary_root / "configs" / "source_manifest.json").write_text("{}", encoding="utf-8")
            with patch.object(runner, "ROOT", temporary_root), patch.object(sys, "argv", ["run_research.py", "--require-exact-replay"]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 2)
            result = json.loads((temporary_root / "output" / "research_results.json").read_text())
            self.assertEqual(result["status"], "REVIEW REQUIRED")
            self.assertEqual(result["replay_difference_count"], 14)

    def test_late_failure_invalidates_already_written_comparisons(self):
        with tempfile.TemporaryDirectory(prefix="structured_credit_test_") as directory:
            temporary_root = Path(directory)
            (temporary_root / "data").mkdir()
            (temporary_root / "configs").mkdir()
            (temporary_root / "data" / "certificates.json").write_text(json.dumps(self.fixture), encoding="utf-8")
            (temporary_root / "configs" / "source_manifest.json").write_text("{}", encoding="utf-8")
            with patch.object(runner, "ROOT", temporary_root), patch.object(sys, "argv", ["run_research.py"]), patch.object(runner, "render", side_effect=ValueError("render failed")), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            output = temporary_root / "output"
            self.assertEqual(json.loads((output / "research_results.json").read_text())["status"], "ERROR")
            for name in ("reconciliation_checks.csv", "replay_comparison.csv"):
                self.assertEqual(len((output / name).read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
