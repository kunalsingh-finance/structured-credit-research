"""Package and verify the inspectable research release using only Python's standard library.

The release opens without the source archive, SQLite panel, Node runtime or Python
dependencies. Its integrity checks prove version consistency and delivery, not
financial reconciliation or investment suitability.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import gzip
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "structured-credit-research"
DELIVERABLES = (
    "output/research_report.html", "output/pdf/credit_memo.pdf",
    "output/outputs/credit_research/cashflow_workbook.xlsx",
)
EXECUTED_SOURCES = ("data/raw/legal/d943115dex991.htm.gz", "data/raw/legal/d943115dex41.htm.gz")
DIRECTORIES = (".github", "configs", "credit_research", "data", "docs",
               "report_assets", "scripts", "tests", "output")
SKIP_PARTS = {"raw", "qa", "releases", "node_modules", "__pycache__",
              "bounded_fixture", ".venv", "loan_level"}
EXTENSIONS = {".py", ".mjs", ".md", ".json", ".css", ".js", ".html",
              ".pdf", ".xlsx", ".jpg", ".png", ".gz", ".yml", ".yaml"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read_snapshot(root: Path) -> dict[str, bytes]:
    snapshot = {}
    for name in ("README.md", "requirements.txt", ".gitattributes", ".gitignore"):
        path = root / name
        if path.exists():
            snapshot[name] = path.read_bytes()
    for directory in DIRECTORIES:
        base = root / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(root)
            if any(part in SKIP_PARTS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Unexpected symbolic link in release: {relative}")
            if path.is_file() and path.suffix.lower() in EXTENSIONS:
                if path.name.endswith(".inspect.ndjson"):
                    continue
                snapshot[relative.as_posix()] = path.read_bytes()
    # Only these two small executed official documents accompany the release;
    # the bulk loan tapes and other raw source archives remain excluded.
    for name in EXECUTED_SOURCES:
        path = root / name
        if path.is_symlink():
            raise ValueError(f"Unexpected symbolic link in executed source: {name}")
        snapshot[name] = path.read_bytes()
    return snapshot


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.external_runtime = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("href", "src"):
            value = attrs.get(key)
            if value:
                self.references.append(value)
                if tag in {"script", "img", "iframe", "link"} and urlsplit(value).scheme in {"http", "https"}:
                    self.external_runtime.append(value)


def check_html_links(snapshot: dict[str, bytes]) -> dict:
    local = []
    external = 0
    for name, raw in snapshot.items():
        if not name.endswith(".html"):
            continue
        parser = Links()
        parser.feed(raw.decode("utf-8"))
        if parser.external_runtime:
            raise ValueError(f"External runtime dependency in {name}: {parser.external_runtime}")
        for reference in parser.references:
            url = urlsplit(reference)
            if url.scheme or url.netloc:
                external += 1
                continue
            if not url.path:
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
            if target.startswith("../") or target.startswith("/") or target not in snapshot:
                raise ValueError(f"Broken or escaping local link: {name} -> {reference}")
            local.append({"page": name, "reference": reference, "target": target})
    return {"local_references": local, "external_source_references": external,
            "external_runtime_dependencies": 0}


def check_version(snapshot: dict[str, bytes]) -> dict:
    pack_raw = snapshot["output/platform_results.json"]
    pack = json.loads(pack_raw)
    status = json.loads(snapshot["output/platform_run_status.json"])
    expected = digest(pack_raw)
    if (status.get("status") != "SUCCESS" or status.get("results_sha256") != expected
            or status.get("built_at") != pack.get("generated_at")):
        raise ValueError("Research results lack a matching successful generation record")
    # Generation success does not replace these failed research gates.
    if not pack.get("research_gates") or not pack.get("status"):
        raise ValueError("Research status and financial gates must be preserved")
    qa = json.loads(snapshot["output/artifact_verification.json"])
    if qa.get("results_sha256") != expected or qa.get("results_version") != pack["generated_at"]:
        raise ValueError("Artifact verification does not describe this research version")
    for name in DELIVERABLES:
        if qa.get("artifact_sha256", {}).get(name) != digest(snapshot[name]):
            raise ValueError(f"Artifact differs from its verification record: {name}")
    release_code = pack.get("release_code_sha256")
    if not isinstance(release_code, dict) or not release_code:
        raise ValueError("Research results must record the model code identities")
    for name, expected_hash in release_code.items():
        if name not in snapshot or digest(snapshot[name]) != expected_hash:
            raise ValueError(f"Model code differs from the recorded research build: {name}")
    for name, expected_hash in qa.get("artifact_builder_sha256", {}).items():
        if name not in snapshot or digest(snapshot[name]) != expected_hash:
            raise ValueError(f"Artifact builder differs from its verification record: {name}")
    text = snapshot["output/research_report.html"].decode("utf-8")
    match = re.search(r'<script id="research-data" type="application/json">(.*?)</script>', text, re.DOTALL)
    if not match or json.loads(match.group(1)) != pack:
        raise ValueError("Embedded dashboard evidence differs from platform_results.json")
    sources = json.loads(snapshot["data/source_manifest.json"])["sources"]
    source_checks = []
    for name in EXECUTED_SOURCES:
        matches = [record for record in sources if record.get("archive_path") == name]
        if len(matches) != 1:
            raise ValueError(f"Executed source must have one frozen source record: {name}")
        record = matches[0]
        official_url = "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/" + Path(name).stem
        if record.get("url") != official_url or record.get("kind") != "executed_legal":
            raise ValueError(f"Executed source must be the official transaction document: {name}")
        archived = snapshot[name]
        original = gzip.decompress(archived)
        if (digest(archived) != record.get("sha256_archive") or len(archived) != record.get("archive_byte_count")
                or digest(original) != record.get("sha256_original_bytes") or len(original) != record.get("original_byte_count")):
            raise ValueError(f"Executed original/archive byte identity differs: {name}")
        source_checks.append(name)
    return {"results_version": pack["generated_at"], "results_sha256": expected,
            "research_status": pack["status"], "research_gates": pack["research_gates"],
            "release_model_code_files_checked": len(release_code), "executed_source_hash_chains_checked": source_checks}


def start_page(version: dict) -> bytes:
    date = html.escape(version["results_version"])
    status = html.escape(version["research_status"].capitalize())
    return f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Structured Credit Research — start here</title>
<style>body{{max-width:850px;margin:60px auto;padding:0 24px;background:#f7f5ef;color:#17293a;font:18px/1.6 system-ui,sans-serif}}h1{{font-size:38px;line-height:1.15}}a{{color:#075e76}}li{{margin:12px 0}}.status{{padding:20px;background:#fff3dd;border-left:5px solid #ac7616}}small{{color:#536472}}</style>
<p>KUNAL SINGH / INDEPENDENT AUTO-ABS RESEARCH</p><h1>Structured Credit Risk and Cash-Flow Platform</h1>
<p class="status"><strong>{status}.</strong> Internal cash and accounting controls are implemented, but exact tape/certificate cash reconciliation and contractual replay retain material source-definition exceptions. These scenarios are illustrative research, not validated investment forecasts.</p>
<ul><li><a href="output/research_report.html">Open the interactive research dashboard</a></li>
<li><a href="output/outputs/credit_research/cashflow_workbook.xlsx">Open the formula-based Excel cash-flow workbook</a></li>
<li><a href="output/pdf/credit_memo.pdf">Read the two-page credit memo</a></li>
<li><a href="docs/RESEARCH_DESIGN.md">Read the research design and acceptance gates</a></li>
<li><a href="docs/COMPLETION_AUDIT.md">Inspect the completion audit and unresolved gates</a></li>
<li><a href="docs/RELEASE.md">View integrity, reproduction and delivery instructions</a></li></ul>
<p>Extract the complete ZIP before opening these files. The dashboard embeds its data and code, so it works locally without the 1.19 GB loan panel, source archive, Python, Node or an internet connection. External SEC and New York Fed source links require internet access. The Excel file requires a compatible spreadsheet application.</p>
<p>Yield changes reprice saved bond cash flows. Credit assumptions require the research pipeline and the omitted source data. Model comparisons show mixed performance: better default/interest errors do not imply better principal/runoff forecasts.</p>
<small>Saved research version: {date}. Codex-assisted independent project; no issuer affiliation or official rating.</small></html>'''.encode("utf-8")


def valid_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (not path.is_absolute() and ".." not in path.parts and "\\" not in name
            and ":" not in name and path.parts and path.parts[0] == PREFIX)


def verify_zip(path: Path) -> dict:
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) != len({n.casefold() for n in names}):
            raise ValueError("Duplicate or case-colliding ZIP entry")
        if not all(valid_name(n) for n in names):
            raise ValueError("ZIP contains an unsafe archive path")
        manifest_name = f"{PREFIX}/RELEASE_MANIFEST.json"
        manifest = json.loads(archive.read(manifest_name))
        expected_names = {f"{PREFIX}/{name}" for name in manifest["files"]} | {manifest_name}
        if set(names) != expected_names:
            raise ValueError("ZIP inventory differs from the release manifest")
        snapshot = {}
        for name, record in manifest["files"].items():
            raw = archive.read(f"{PREFIX}/{name}")
            if len(raw) != record["bytes"] or digest(raw) != record["sha256"]:
                raise ValueError(f"ZIP content hash differs: {name}")
            snapshot[name] = raw
    version = check_version(snapshot)
    if manifest["results_sha256"] != version["results_sha256"]:
        raise ValueError("Release manifest describes another results version")
    links = check_html_links(snapshot)
    return {"zip": str(path), "zip_sha256": digest(path.read_bytes()), "zip_bytes": path.stat().st_size,
            "files_verified": len(snapshot), "local_links_verified": len(links["local_references"]),
            "version": version, "verification_scope": "Saved file integrity and delivery; financial gates unchanged"}


def build(root: Path, output: Path) -> dict:
    snapshot = read_snapshot(root)
    version = check_version(snapshot)
    snapshot["START_HERE.html"] = start_page(version)
    links = check_html_links(snapshot)
    manifest = {"schema_version": 1, **version,
        "release_scope": "Offline inspection, source/code audit and bounded-fixture reproduction",
        "excluded": ["bulk raw SEC corpus except two explicitly included executed documents", "SQLite loan panel", "Python/Node runtimes", "ignored manual QA workspace"],
        "limitations": "Financial gate failures are preserved. Included verification is recorded evidence, not a rerun of omitted raw data.",
        "html_delivery_checks": links,
        "files": {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in sorted(snapshot.items())}}
    snapshot["RELEASE_MANIFEST.json"] = json_bytes(manifest)
    stamp = datetime.fromisoformat(version["results_version"].replace("Z", "+00:00"))
    zip_date = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(snapshot.items()):
            info = ZipInfo(f"{PREFIX}/{name}", date_time=zip_date)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    result = verify_zip(temporary)
    temporary.replace(output)
    result["zip"] = str(output)
    output.with_suffix(output.suffix + ".sha256").write_text(f'{result["zip_sha256"]}  {output.name}\n', encoding="ascii")
    output.with_suffix(output.suffix + ".verification.json").write_bytes(json_bytes(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/releases/structured_credit_research.zip")
    parser.add_argument("--verify", type=Path, help="Verify an existing ZIP instead of building")
    args = parser.parse_args()
    try:
        result = verify_zip(args.verify) if args.verify else build(ROOT, args.output)
    except (KeyError, ValueError, OSError) as error:
        parser.exit(2, f"Release verification failed: {error}\n")
    print(json.dumps({key: value for key, value in result.items() if key != "version"}, indent=2))


if __name__ == "__main__":
    main()
