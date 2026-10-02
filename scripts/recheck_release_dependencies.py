"""Check for changed public release evidence without altering the frozen corpus.

Unavailable endpoints are unknown, never evidence that no filings exist.
Successful current bytes are archived separately. New records require review;
this script cannot pass a reconciliation gate merely by finding no change.
"""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from acquire_data import DEFAULT_USER_AGENT

ROOT = Path(__file__).resolve().parents[1]
FILERS = (2016948, 2063979, 1259380, 1170010, 1601902)
KEY_DISCLOSURES = (
    "https://www.sec.gov/Archives/edgar/data/2063979/000206397926000045/exhibit103november2021.xml",
    "https://www.sec.gov/Archives/edgar/data/2063979/000206397926000047/a2025-2ex991091526.htm",
)


def main():
    sources = []
    for name in ("source_manifest.json", "rate_amendment_source_manifest.json"):
        sources.extend(json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))["sources"])
    previous_sources = {source["url"]: source for source in sources}
    urls = [f"https://data.sec.gov/submissions/CIK{cik:010}.json" for cik in FILERS]
    urls.extend(KEY_DISCLOSURES)
    now = datetime.now(timezone.utc)
    directory = ROOT / "data/raw/dependency_recheck" / now.strftime("%Y%m%dT%H%M%S%fZ")
    checks = []
    for index, url in enumerate(urls, 1):
        entry = {"url": url, "checked_at_utc": datetime.now(timezone.utc).isoformat()}
        previous = previous_sources.get(url)
        if previous:
            entry["previous_original_sha256"] = previous["sha256_original_bytes"]
        try:
            request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT,
                "Accept-Encoding": "identity", "Accept": "*/*"})
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read()
                entry["http_status"] = response.status
            original_hash = hashlib.sha256(raw).hexdigest()
            entry.update(original_sha256=original_hash, original_byte_count=len(raw),
                same_original_bytes_as_frozen_source=None if previous is None else
                    original_hash == previous["sha256_original_bytes"])
            if "/submissions/" in url:
                document = json.loads(raw)
                recent = document["filings"]["recent"]
                entry["latest_filing_date"] = max(recent["filingDate"], default=None)
                entry["history_files"] = document["filings"].get("files", [])
                if previous:
                    prior_bytes = gzip.decompress((ROOT / previous["archive_path"]).read_bytes())
                    if hashlib.sha256(prior_bytes).hexdigest() != previous["sha256_original_bytes"]:
                        raise ValueError("Frozen submissions archive failed original-byte verification")
                    before = set(json.loads(prior_bytes)["filings"]["recent"]["accessionNumber"])
                    after = set(recent["accessionNumber"])
                    entry["new_accession_records"] = [{key: recent[key][row] for key in
                        ("accessionNumber", "filingDate", "acceptanceDateTime", "form", "primaryDocument")}
                        for row, accession in enumerate(recent["accessionNumber"]) if accession not in before]
                    entry["previous_accessions_missing_now"] = sorted(before - after)
            archived = gzip.compress(raw, compresslevel=3, mtime=0)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"source_{index:02}.gz"
            path.write_bytes(archived)
            entry.update(availability="RETRIEVED", archive_path=str(path.relative_to(ROOT)),
                archive_sha256=hashlib.sha256(archived).hexdigest(), archive_byte_count=len(archived))
        except urllib.error.HTTPError as error:
            entry.update(http_status=error.code, availability="NOT_RETRIEVED",
                finding="HTTP status is an access/inventory observation, not evidence of no filings or corrections")
        except Exception as error:
            entry.update(availability="NOT_RETRIEVED", error_type=type(error).__name__,
                error=str(error), finding="Current source state is unverified; retain failed gates")
        checks.append(entry)
        print(json.dumps({key: value for key, value in entry.items() if key != "history_files"}), flush=True)
        time.sleep(.3)
    raw_results = (ROOT / "output/platform_results.json").read_bytes()
    results = json.loads(raw_results)
    report = {"schema_version": 1, "checked_at_utc": now.isoformat(),
        "results_sha256": hashlib.sha256(raw_results).hexdigest(),
        "results_version": results["generated_at"], "research_gates": results["research_gates"],
        "sources": checks, "conclusion": "This finite recheck does not change source reconciliation or exact replay gates. Changed or newly indexed sources require independent review; unavailable sources do not establish absence."}
    (ROOT / "output/release_dependency_recheck.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
