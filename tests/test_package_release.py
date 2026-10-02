"""Delivery controls prevent stale, incomplete or altered research ZIPs."""
from __future__ import annotations

import importlib.util
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/package_release.py"
spec = importlib.util.spec_from_file_location("package_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def fixture(root):
    pack = {"generated_at": "2026-10-02T12:18:59+00:00",
            "status": "DEVELOPMENT RESEARCH WITH UNRESOLVED SOURCE EXCEPTIONS",
            "research_gates": {"exact_reconciliation": False},
            "release_code_sha256": {"credit_research/model.py": release.digest(b"model code")}}
    raw = release.json_bytes(pack)
    artifacts = {"output/research_report.html":
                 ('<a href="pdf/credit_memo.pdf">Memo</a><script id="research-data" type="application/json">'
                  + json.dumps(pack) + '</script>').encode(),
                 "output/pdf/credit_memo.pdf": b"fixture memo",
                 "output/outputs/credit_research/cashflow_workbook.xlsx": b"fixture workbook"}
    snapshot = {
        "output/platform_results.json": raw,
        "output/platform_run_status.json": release.json_bytes({"status": "SUCCESS", "results_sha256": release.digest(raw), "built_at": pack["generated_at"]}),
        "output/artifact_verification.json": release.json_bytes({"results_sha256": release.digest(raw), "results_version": pack["generated_at"], "artifact_sha256": {name: release.digest(value) for name, value in artifacts.items()}}),
        "credit_research/model.py": b"model code", "docs/RESEARCH_DESIGN.md": b"Research design",
        "docs/COMPLETION_AUDIT.md": b"Full validation remains unresolved",
        "docs/RELEASE.md": b"Delivery instructions", **artifacts}
    legal_sources = []
    for name in release.EXECUTED_SOURCES:
        original = b"executed source fixture"
        archived = gzip.compress(original, compresslevel=3, mtime=0)
        snapshot[name] = archived
        legal_sources.append({"archive_path": name, "kind": "executed_legal",
            "url": "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/" + Path(name).stem,
            "sha256_archive": release.digest(archived), "archive_byte_count": len(archived),
            "sha256_original_bytes": release.digest(original), "original_byte_count": len(original)})
    snapshot["data/source_manifest.json"] = release.json_bytes({"sources": legal_sources})
    for name, value in snapshot.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    return snapshot


class TestPortableRelease(unittest.TestCase):
    def test_saved_outputs_open_without_raw_panel_or_dependencies(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for name in ("data/raw/source.gz", "data/loan_panel.sqlite", "scripts/node_modules/runtime.js", "output/qa/private.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"must not ship")
            target = root / "output/releases/fixture.zip"
            report = release.build(root, target)
            self.assertEqual(report["version"]["research_gates"], {"exact_reconciliation": False})
            with ZipFile(target) as archive:
                names = archive.namelist()
                self.assertIn(f"{release.PREFIX}/START_HERE.html", names)
                self.assertEqual({name for name in names if "/raw/" in name},
                                 {f"{release.PREFIX}/{name}" for name in release.EXECUTED_SOURCES})
                self.assertFalse(any("node_modules" in name or "loan_panel" in name or "qa/" in name for name in names))
            original = target.read_bytes()
            release.build(root, target)
            self.assertEqual(original, target.read_bytes())

    def test_stale_or_changed_deliverable_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = fixture(root)
            snapshot["output/pdf/credit_memo.pdf"] = b"edited after verification"
            with self.assertRaisesRegex(ValueError, "Artifact differs"):
                release.check_version(snapshot)
            snapshot = fixture(root)
            snapshot["output/platform_run_status.json"] = b'{"status":"BUILDING"}'
            with self.assertRaisesRegex(ValueError, "matching successful"):
                release.check_version(snapshot)
            snapshot = fixture(root)
            snapshot[release.EXECUTED_SOURCES[0]] = gzip.compress(b"changed official document", mtime=0)
            with self.assertRaisesRegex(ValueError, "original/archive byte identity differs"):
                release.check_version(snapshot)

    def test_code_change_and_dashboard_version_change_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = fixture(root)
            snapshot["credit_research/model.py"] = b"different model"
            with self.assertRaisesRegex(ValueError, "Model code differs"):
                release.check_version(snapshot)
            snapshot = fixture(root)
            name = "output/research_report.html"
            snapshot[name] = snapshot[name].replace(b"DEVELOPMENT RESEARCH", b"FALSELY COMPLETE RESEARCH")
            qa = json.loads(snapshot["output/artifact_verification.json"])
            qa["artifact_sha256"][name] = release.digest(snapshot[name])
            snapshot["output/artifact_verification.json"] = release.json_bytes(qa)
            with self.assertRaisesRegex(ValueError, "Embedded dashboard evidence differs"):
                release.check_version(snapshot)

    def test_missing_link_or_network_runtime_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, "Broken or escaping"):
            release.check_html_links({"index.html": b'<a href="missing.pdf">Memo</a>'})
        with self.assertRaisesRegex(ValueError, "External runtime"):
            release.check_html_links({"index.html": b'<script src="https://example.com/runtime.js"></script>'})

    def test_hash_tampering_and_unsafe_zip_entry_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            target = root / "release.zip"
            release.build(root, target)
            with ZipFile(target) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            name = f"{release.PREFIX}/output/pdf/credit_memo.pdf"
            contents[name] = b"tampered memo"
            tampered = root / "tampered.zip"
            with ZipFile(tampered, "w", compression=ZIP_DEFLATED) as archive:
                for name, raw in contents.items():
                    archive.writestr(name, raw)
            with self.assertRaisesRegex(ValueError, "content hash differs"):
                release.verify_zip(tampered)
            with ZipFile(target, "a") as archive:
                archive.writestr(f"{release.PREFIX}/../escape.txt", b"not valid")
            with self.assertRaisesRegex(ValueError, "unsafe archive path"):
                release.verify_zip(target)


if __name__ == "__main__":
    unittest.main()
