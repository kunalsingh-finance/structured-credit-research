"""Read saved artifacts and reject stale inputs without changing delivered files."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FILES = [ROOT / "output/research_report.html", ROOT / "output/pdf/credit_memo.pdf",
         ROOT / "output/outputs/credit_research/cashflow_workbook.xlsx"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True, help="Bundled artifact-tool Node executable")
    args = parser.parse_args()
    results_path = ROOT / "output/platform_results.json"
    pack = json.loads(results_path.read_text(encoding="utf-8"))
    expected = digest(results_path)
    run = json.loads((ROOT / "output/platform_run_status.json").read_text())
    assert run["status"] == "SUCCESS" and run["results_sha256"] == expected
    before = {p.relative_to(ROOT).as_posix(): digest(p) for p in FILES}
    # Human UI/layout evidence is versioned separately and cannot be carried
    # automatically into a future rebuild by this numerical verifier.
    manual = json.loads((ROOT / "output/qa/manual_review.json").read_text())
    assert manual["results_sha256"] == expected and manual["artifact_sha256"] == before
    workbook_qa = json.loads((ROOT / "output/qa/workbook/verification.json").read_text())
    artifact_qa = json.loads((ROOT / "output/qa/artifacts/verification.json").read_text())
    for qa in (workbook_qa, artifact_qa):
        assert qa["results_sha256"] == expected and qa["generated_at"] == pack["generated_at"]
    assert workbook_qa["output_sha256"] == digest(FILES[2])
    assert all(digest(Path(path)) == value for path, value in artifact_qa["outputs"].items())
    with ZipFile(FILES[2]) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = [s.attrib["name"] for s in workbook.findall("s:sheets/s:sheet", NS)]
        formula_count = missing = validations = 0
        errors = []
        for name in archive.namelist():
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            root = ET.fromstring(archive.read(name))
            validations += len(root.findall(".//s:dataValidation", NS))
            for cell in root.findall(".//s:c", NS):
                if cell.find("s:f", NS) is not None:
                    formula_count += 1
                    missing += cell.find("s:v", NS) is None
                if cell.attrib.get("t") == "e":
                    errors.append({"part": name, "cell": cell.attrib["r"], "value": cell.findtext("s:v", namespaces=NS)})
        assert len(sheets) == 9 and formula_count > 3000 and missing == 0 and not errors
        assert validations == 5 and any("/charts/chart" in n and n.endswith(".xml") for n in archive.namelist())
    reader = PdfReader(FILES[1])
    assert len(reader.pages) == 2
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert "After-inspection" in text and "287" in text and "76.08" in text
    links = [str(a.get_object()["/A"]["/URI"]) for p in reader.pages for a in p.get("/Annots", [])
             if a.get_object().get("/A", {}).get("/URI")]
    assert len(links) == 2 and all(u.startswith("https://www.sec.gov/Archives/") for u in links)
    temp = ROOT / "tmp/final_guard_tests"
    temp.mkdir(parents=True, exist_ok=True)
    guards = []
    for mode, status in (("BUILDING", {"status": "BUILDING"}),
                         ("hash_mismatch", {"status": "SUCCESS", "results_sha256": "0" * 64, "built_at": pack["generated_at"]})):
        status_path = temp / f"{mode}.json"
        status_path.write_text(json.dumps(status), encoding="utf-8")
        for executable, builder in ((sys.executable, "scripts/build_artifacts.py"),
                                     (args.node, "scripts/build_workbook.mjs")):
            process = subprocess.run([executable, str(ROOT / builder), "--input", str(results_path),
                                      "--run-status", str(status_path)], cwd=ROOT, capture_output=True, text=True)
            assert process.returncode != 0, (builder, mode, "Invalid input unexpectedly accepted")
            assert {p.relative_to(ROOT).as_posix(): digest(p) for p in FILES} == before
            guards.append({"builder": builder, "invalid_input": mode, "rejected": True})
    report = {"results_version": pack["generated_at"], "results_sha256": expected,
              "verified_at": datetime.now(timezone.utc).isoformat(), "artifact_sha256": before,
              "cached_formulas": formula_count, "missing_formula_caches": missing,
              "saved_formula_errors": errors, "xlsx_sheets": sheets,
              "input_validations": validations, "native_chart_retained": True,
              "pdf_pages": len(reader.pages), "pdf_source_links": links,
              "negative_guards": guards, "negative_tests_left_outputs_unchanged": True,
              "independent_numerical_checks": workbook_qa,
              "native_excel_invoked": False,
              "visual_review": manual["visual_review"], "browser_checks": manual["browser_checks"],
              "artifact_builder_sha256": {name: digest(ROOT / name) for name in
                   ("scripts/build_artifacts.py", "scripts/build_workbook.mjs", "scripts/verify_artifacts.py")}}
    path = ROOT / "output/artifact_verification.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / "output/qa/final_artifact_verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verification": str(path), "formulas": formula_count,
                      "formula_errors": len(errors), "guard_tests": len(guards), "pdf_pages": 2}, indent=2))


if __name__ == "__main__":
    main()
