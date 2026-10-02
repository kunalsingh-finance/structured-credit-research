"""Ingestion invariants that prevent source distortion or future-data leakage."""
from __future__ import annotations
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from credit_research.ingest import AUTO_NAMESPACE, iter_auto_assets, money_cents, normalize_asset, parse_certificate_html, verify_archive

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_panel", ROOT / "scripts/build_panel.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def source(period="2025-04-30"):
    return {"deal_id": "TEST", "report_period": period, "acceptance_time": "2025-05-15T14:00:00.000Z", "accession": period}


def asset(period="04-30-2025", **overrides):
    raw = {"assetNumber": "private-scoped-id", "reportingPeriodBeginningDate": period[:3] + "01" + period[5:],
        "reportingPeriodEndingDate": period, "originationDate": "01/2025", "loanMaturityDate": "01/2030",
        "originalLoanAmount": "1000.00", "vehicleValueAmount": "1000.00", "originalLoanTerm": "60",
        "reportingPeriodBeginningLoanBalanceAmount": "1000.00", "reportingPeriodActualEndBalanceAmount": "990.00",
        "actualPrincipalCollectedAmount": "10.00", "actualInterestCollectedAmount": "2.00", "obligorCreditScore": "603.5",
        "currentDelinquencyStatus": "0", "reportingPeriodInterestRatePercentage": "0.08", "remainingTermToMaturityNumber": "57"}
    raw.update(overrides)
    return raw


class IngestTests(unittest.TestCase):
    def test_signed_credit_balances_missing_fields_and_decimal_scores_preserved(self):
        row = normalize_asset(asset(reportingPeriodActualEndBalanceAmount="-0.41", otherPrincipalAdjustmentAmount="-3.25"), source())
        self.assertEqual(row["end_balance_cents"], -41)
        self.assertEqual(row["other_principal_adjustment_cents"], -325)
        self.assertEqual(row["credit_score"], 603.5)
        self.assertIsNone(row["chargeoff_cents"])
        self.assertIsNone(row["recovery_cents"])
        self.assertEqual(row["interest_rate_pct"], 8.0)
        self.assertEqual(row["acceptance_time"], source()["acceptance_time"])
        row = normalize_asset(asset(obligorCreditScore="NONE", recoveredAmount="0.00"), source())
        self.assertIsNone(row["credit_score"])
        self.assertEqual(row["recovery_cents"], 0)

    def test_fractional_cents_and_metadata_mismatches_rejected(self):
        with self.assertRaises(ValueError):
            money_cents("1.001")
        with self.assertRaises(ValueError):
            normalize_asset(asset(), source("2025-05-31"))

    def test_xml_rejects_namespace_drift_and_duplicate_loan_periods(self):
        record = "<assets><assetNumber>A</assetNumber><reportingPeriodEndingDate>04-30-2025</reportingPeriodEndingDate></assets>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tape.xml.gz"
            for namespace, records in (("http://wrong", record), (AUTO_NAMESPACE, record * 2)):
                with gzip.open(path, "wt") as stream:
                    stream.write(f'<assetData xmlns="{namespace}">{records}</assetData>')
                with self.assertRaises(ValueError):
                    list(iter_auto_assets(path))

    def test_schema_repeating_zero_balance_codes_preserved(self):
        row = normalize_asset(asset(zeroBalanceCode=["1", "4"]), source())
        self.assertEqual(row["zero_balance_code"], "1|4")

    def test_original_byte_hash_cannot_be_replaced_by_archive_hash(self):
        original = b"<assetData />\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.xml.gz"
            path.write_bytes(gzip.compress(original, mtime=0))
            metadata = {"sha256_archive": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sha256_original_bytes": hashlib.sha256(original).hexdigest(), "original_byte_count": len(original)}
            verify_archive(path, metadata)
            with self.assertRaises(ValueError):
                verify_archive(path, {**metadata, "sha256_original_bytes": metadata["sha256_archive"]})

    def test_first_defaults_and_period_recoveries_not_repeated(self):
        rows = [normalize_asset(asset("04-30-2025", chargedoffPrincipalAmount="1000.00", reportingPeriodActualEndBalanceAmount="0.00", zeroBalanceCode="4", zeroBalanceEffectiveDate="04/2025", recoveredAmount="10.00"), source()),
                normalize_asset(asset("05-31-2025", chargedoffPrincipalAmount="1000.00", reportingPeriodBeginningLoanBalanceAmount="0.00", reportingPeriodActualEndBalanceAmount="0.00", zeroBalanceCode="4", zeroBalanceEffectiveDate="04/2025", recoveredAmount="20.00"), source("2025-05-31")),
                normalize_asset(asset("06-30-2025", assetNumber="prepaid", chargedoffPrincipalAmount="0.00", zeroBalanceCode="1", zeroBalanceEffectiveDate="06/2025", reportingPeriodActualEndBalanceAmount="0.00", actualPrincipalCollectedAmount="1000.00"), source("2025-06-30")),
                normalize_asset(asset("06-30-2025", assetNumber="repurchased", zeroBalanceCode=["1", "3"], zeroBalanceEffectiveDate="06/2025", loanMaturityDate="06/2025", reportingPeriodActualEndBalanceAmount="0.00"), source("2025-06-30"))]
        with sqlite3.connect(":memory:") as db:
            builder.create_tables(db, rows[0].keys())
            columns = list(rows[0])
            db.executemany("INSERT INTO loan_month VALUES(" + ",".join("?" for _ in columns) + ")", [tuple(r[k] for k in columns) for r in rows])
            builder.derive_events(db)
            self.assertEqual(db.execute("SELECT SUM(first_default_event) FROM loan_month").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT SUM(recovery_cents) FROM loan_month").fetchone()[0], 3000)
            self.assertEqual(db.execute("SELECT prepayment_event FROM loan_month WHERE loan_id='prepaid'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT prepayment_event,maturity_event,repurchase_event FROM loan_month WHERE loan_id='repurchased'").fetchone(), (0, 0, 1))

    def test_archived_known_certificate_matches_independent_manual_fixture(self):
        path = ROOT / "tests/fixtures/sec_certificates/manifest.json"
        sources = json.loads(path.read_text())["sources"]
        fixture = json.loads((ROOT / "data/certificates.json").read_text())["certificates"]
        for expected in fixture:
            archived = next(s for s in sources if s["kind"] == "certificate" and s["accession"] == expected["accession"])
            verify_archive(ROOT / archived["archive_path"], archived)
            with gzip.open(ROOT / archived["archive_path"], "rb") as stream:
                result = parse_certificate_html(stream.read(), archived, expected["replay_inputs"]["prior_distribution_date"])
            self.assertEqual(result["amounts"], expected["amounts"])
            self.assertEqual(result["expected"], expected["expected"])


if __name__ == "__main__":
    unittest.main()
