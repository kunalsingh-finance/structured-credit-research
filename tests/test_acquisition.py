"""Frozen-source restoration must not turn a changed disclosure into old evidence."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import acquire_data


class Response(io.BytesIO):
    headers = {"Content-Type": "application/xml"}


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.addCleanup(patch.stopall)
        patch.object(acquire_data, "ROOT", self.root).start()
        patch.object(acquire_data.time, "sleep").start()
        self.url = "https://www.sec.gov/Archives/test.xml"
        self.path = self.root / "data/raw/test.xml.gz"
        self.manifest = self.root / "data/sources.json"
        self.downloader = acquire_data.Downloader("Test Research test@example.org", self.manifest)

    def acquire(self, raw):
        with patch.object(acquire_data.urllib.request, "urlopen", return_value=Response(raw)), contextlib.redirect_stdout(io.StringIO()):
            return self.downloader.archive(self.url, self.path, kind="fixture")

    def test_new_source_has_one_verified_manifest_entry(self):
        entry = self.acquire(b"<source>initial</source>")
        self.assertEqual(len(json.loads(self.manifest.read_text())["sources"]), 1)
        self.assertEqual(self.downloader.by_url[self.url], entry)
        self.assertTrue(self.path.exists())

    def test_cache_hit_does_not_request_source(self):
        expected = self.acquire(b"<source>initial</source>")
        with patch.object(acquire_data.urllib.request, "urlopen") as request:
            actual = self.downloader.archive(self.url, self.path)
        self.assertEqual(actual, expected)
        request.assert_not_called()

    def test_restore_preserves_frozen_manifest_and_uses_recorded_path(self):
        raw = b"<source>initial</source>"
        expected = self.acquire(raw)
        original_archive = self.path.read_bytes()
        original_manifest = self.manifest.read_bytes()
        self.path.unlink()
        with patch.object(acquire_data.urllib.request, "urlopen", return_value=Response(raw)), contextlib.redirect_stdout(io.StringIO()):
            restored = self.downloader.archive(self.url, self.root / "different/location.gz", kind="replacement")
        self.assertEqual(restored, expected)
        self.assertEqual(self.path.read_bytes(), original_archive)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertEqual(len(self.downloader.manifest["sources"]), 1)
        self.assertFalse((self.root / "different/location.gz").exists())

    def test_changed_original_is_rejected_without_manifest_change(self):
        self.acquire(b"<source>initial</source>")
        original_manifest = self.manifest.read_bytes()
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "differs from the frozen original"):
            self.acquire(b"<source>changed</source>")
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertFalse(self.path.exists())
        self.assertTrue(self.path.with_suffix(self.path.suffix + ".part").exists())

    def test_incompatible_archive_identity_is_rejected(self):
        raw = b"<source>initial</source>"
        self.acquire(raw)
        self.path.unlink()
        self.downloader.by_url[self.url]["sha256_archive"] = "0" * 64
        self.downloader.save()
        original_manifest = self.manifest.read_bytes()
        with self.assertRaisesRegex(ValueError, "compressed bytes differ"):
            self.acquire(raw)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertFalse(self.path.exists())

    def test_corrupt_cache_is_rejected_without_download(self):
        self.acquire(b"<source>initial</source>")
        self.path.write_bytes(b"changed cache")
        with patch.object(acquire_data.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(ValueError, "Cached source archive changed"):
                self.downloader.archive(self.url, self.path)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
