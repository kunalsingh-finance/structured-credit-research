"""Archive public SEC sources with original-byte and gzip hashes.

SEC accepts fewer than ten requests per second. This sequential downloader uses
an identifying User-Agent, 0.25-second spacing, bounded retries, and resumable
per-document checkpoints. Pre-offering tapes and future accepted filings are
excluded. XML bytes are streamed into gzip; no 250MB document is loaded in RAM.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import io
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_USER_AGENT = "Kunal Singh StructuredCreditResearch ks0000477@gmail.com"
DEALS = {"CAOT-2024-2": (2016948, "2024-04-30"), "CAOT-2025-2": (2063979, "2025-04-30")}


class Downloader:
    def __init__(self, user_agent: str, manifest: Path):
        self.user_agent = user_agent
        self.manifest_path = manifest
        self.manifest = json.loads(manifest.read_text()) if manifest.exists() else {
            "schema_version": 1, "status": "ARCHIVED_ORIGINAL_SEC_BYTES", "sources": []}
        self.by_url = {s["url"]: s for s in self.manifest["sources"]}

    def save(self):
        self.manifest["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.manifest_path)

    def archive(self, url, path: Path, **metadata):
        existing = self.by_url.get(url)
        if existing and (ROOT / existing["archive_path"]).exists():
            cached_path = ROOT / existing["archive_path"]
            cached_hash = hashlib.sha256()
            with cached_path.open("rb") as cached:
                while chunk := cached.read(1024 * 1024):
                    cached_hash.update(chunk)
            if cached_hash.hexdigest() != existing["sha256_archive"] or cached_path.stat().st_size != existing["archive_byte_count"]:
                raise ValueError(f"Cached source archive changed: {cached_path}; preserve evidence and reacquire explicitly")
            return existing
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        for attempt in range(3):
            try:
                time.sleep(0.25)
                req = urllib.request.Request(url, headers={"User-Agent": self.user_agent,
                    "Accept-Encoding": "identity", "Accept": "*/*"})
                digest = hashlib.sha256()
                count = 0
                with urllib.request.urlopen(req, timeout=90) as response:
                    headers = dict(response.headers)
                    with temporary.open("wb") as target, gzip.GzipFile(
                            fileobj=target, mode="wb", filename="", mtime=0, compresslevel=3) as archive:
                        while True:
                            block = response.read(1024 * 1024)
                            if not block:
                                break
                            digest.update(block)
                            count += len(block)
                            archive.write(block)
                temporary.replace(path)
                archive_digest = hashlib.sha256()
                with path.open("rb") as archived:
                    while chunk := archived.read(1024 * 1024):
                        archive_digest.update(chunk)
                entry = {"url": url, "archive_path": path.relative_to(ROOT).as_posix(),
                    "sha256_original_bytes": digest.hexdigest(), "original_byte_count": count,
                    "sha256_archive": archive_digest.hexdigest(), "archive_byte_count": path.stat().st_size,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "http_content_type": headers.get("Content-Type"),
                    "http_last_modified": headers.get("Last-Modified"), **metadata}
                self.manifest["sources"].append(entry)
                self.by_url[url] = entry
                self.save()
                print(f"Archived {metadata.get('deal_id', '')} {metadata.get('report_period', '')} "
                      f"{metadata.get('kind', '')}: {count:,} -> {path.stat().st_size:,} bytes", flush=True)
                return entry
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt == 2:
                    raise
                print(f"Retry {attempt + 1}: {url}: {error}", flush=True)
                time.sleep(2 * (attempt + 1))

    def json(self, url, path, **metadata):
        entry = self.archive(url, path, **metadata)
        with gzip.open(ROOT / entry["archive_path"], "rt", encoding="utf-8") as stream:
            return json.load(stream)


def filing_records(document):
    recent = document["filings"]["recent"]
    return [{key: values[index] for key, values in recent.items()}
            for index in range(len(recent["accessionNumber"]))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT))
    parser.add_argument("--through", default="2026-10-02", help="UTC acceptance cutoff; excludes future filings")
    parser.add_argument("--certificates-only", action="store_true")
    parser.add_argument("--max-periods", type=int, default=0, help="Earliest N actual periods per deal; 0 means all")
    args = parser.parse_args()
    downloader = Downloader(args.user_agent, ROOT / "data/source_manifest.json")
    selected = []
    for deal, (cik, first_period) in DEALS.items():
        submission = downloader.json(f"https://data.sec.gov/submissions/CIK{cik:010}.json",
            ROOT / f"data/raw/{deal}/submissions.json.gz", kind="submissions", deal_id=deal, cik=cik)
        filings = filing_records(submission)
        for old in submission["filings"].get("files", []):
            older = downloader.json("https://data.sec.gov/submissions/" + old["name"],
                ROOT / f"data/raw/{deal}/{old['name']}.gz", kind="submissions_history", deal_id=deal, cik=cik)
            filings.extend({key: values[index] for key, values in older.items()}
                           for index in range(len(older["accessionNumber"])))
        eligible = [f for f in filings if f["form"] in {"10-D", "10-D/A", "ABS-EE", "ABS-EE/A"}
                    and f["reportDate"] >= first_period and f["acceptanceDateTime"][:10] <= args.through]
        periods = sorted({f["reportDate"] for f in eligible})
        if args.max_periods:
            periods = periods[:args.max_periods]
        selected.extend((deal, cik, f) for f in eligible if f["reportDate"] in periods)
        if deal == "CAOT-2025-2":
            legal = next(f for f in filings if f["accessionNumber"] == "0001193125-25-111714")
            base = "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/"
            for name in ["d943115d8k.htm", "d943115dex41.htm", "d943115dex42.htm", "d943115dex991.htm",
                         "d943115dex992.htm", "d943115dex993.htm", "d943115dex994.htm"]:
                downloader.archive(base + name, ROOT / f"data/raw/legal/{name}.gz", kind="executed_legal",
                    deal_id=deal, accession=legal["accessionNumber"], acceptance_time=legal["acceptanceDateTime"],
                    filing_date=legal["filingDate"], form=legal["form"])
            prospectus = next(f for f in filings if f["accessionNumber"] == "0001193125-25-099841")
            downloader.archive("https://www.sec.gov/Archives/edgar/data/2063979/000119312525099841/d30805d424b5.htm",
                ROOT / "data/raw/legal/d30805d424b5.htm.gz", kind="final_prospectus", deal_id=deal,
                accession=prospectus["accessionNumber"], acceptance_time=prospectus["acceptanceDateTime"],
                filing_date=prospectus["filingDate"], form=prospectus["form"])
        else:
            for accession, cik_path, name, kind in [
                ("0001193125-24-109815", 1259380, "d801955dex991.htm", "executed_legal"),
                ("0001193125-24-102541", 2016948, "d814307d424b5.htm", "final_prospectus")]:
                filing = next(f for f in filings if f["accessionNumber"] == accession)
                base = f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession.replace('-', '')}/"
                downloader.archive(base + name, ROOT / f"data/raw/legal/{name}.gz", kind=kind, deal_id=deal,
                    accession=accession, acceptance_time=filing["acceptanceDateTime"],
                    filing_date=filing["filingDate"], form=filing["form"])
    # Download the small complete certificate set first; then large tapes.
    selected.sort(key=lambda item: (0 if item[2]["form"].startswith("10-D") else 1, item[0], item[2]["reportDate"], item[2]["acceptanceDateTime"]))
    for deal, cik, filing in selected:
        if args.certificates_only and not filing["form"].startswith("10-D"):
            continue
        accession = filing["accessionNumber"]
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
        metadata = {"deal_id": deal, "cik": cik, "accession": accession,
            "form": filing["form"], "report_period": filing["reportDate"],
            "acceptance_time": filing["acceptanceDateTime"], "filing_date": filing["filingDate"],
            "is_amendment": filing["form"].endswith("/A")}
        directory = downloader.json(base + "index.json", ROOT / f"data/raw/{deal}/{accession}/index.json.gz",
            kind="filing_directory", **metadata)
        items = directory["directory"]["item"]
        if filing["form"].startswith("10-D"):
            names = [(i["name"], "certificate") for i in items
                     if "ex991" in i["name"].lower() and i["name"].endswith((".htm", ".html"))]
        else:
            names = [(i["name"], "asset_explanatory" if "exhibit103" in i["name"].lower() else "loan_tape")
                     for i in items if i["name"].endswith(".xml")]
        if not names:
            raise ValueError(f"No expected exhibits in {accession}; inspect actual filing directory")
        for name, kind in names:
            downloader.archive(base + name, ROOT / f"data/raw/{deal}/{accession}/{name}.gz", kind=kind, **metadata)
    schema = downloader.archive("https://www.sec.gov/info/edgar/specifications/absxml-1.9.zip",
        ROOT / "data/raw/schema/absxml-1.9.zip.gz", kind="official_xml_schema", version="1.9", implementation_date="2021-02-25")
    with gzip.open(ROOT / schema["archive_path"], "rb") as stream:
        package = zipfile.ZipFile(io.BytesIO(stream.read()))
    nested = zipfile.ZipFile(io.BytesIO(package.read("ABS XML Schema Files.zip")))
    for name in nested.namelist():
        if name in {"eis_ABS_AutoLoanAssetData.xsd", "eis_ABS_Common.xsd", "eis_Common.xsd", "eis_stateCodes.xsd"}:
            (ROOT / "data/raw/schema" / name).write_bytes(nested.read(name))
    print("Source acquisition completed", flush=True)


if __name__ == "__main__":
    # A second downloader must not overwrite source checkpoints while one runs.
    lock = ROOT / "data/.acquisition.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = lock.open("x")
    except FileExistsError as error:
        raise RuntimeError("An acquisition lock exists; inspect its process before starting another downloader") from error
    try:
        with handle:
            handle.write(str(os.getpid()))
        main()
    finally:
        lock.unlink(missing_ok=True)
