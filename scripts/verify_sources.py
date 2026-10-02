"""Independently read and verify every archived/original-byte hash and size."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from credit_research.ingest import verify_archive


def main():
    manifest_path = ROOT / "data/source_manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    verified = []
    for index, source in enumerate(manifest["sources"], 1):
        verify_archive(ROOT / source["archive_path"], source)
        verified.append({"url": source["url"], "sha256_original_bytes": source["sha256_original_bytes"],
            "sha256_archive": source["sha256_archive"], "status": "PASS"})
        if index % 20 == 0:
            print(f"Verified {index}/{len(manifest['sources'])} full compressed/original hash chains", flush=True)
    result = {"status": "PASS", "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "source_count": len(verified), "original_bytes_verified": sum(s["original_byte_count"] for s in manifest["sources"]),
        "archive_bytes_verified": sum(s["archive_byte_count"] for s in manifest["sources"]), "sources": verified}
    (ROOT / "data/source_verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: verified all {len(verified)} sources, both original and archive bytes", flush=True)


if __name__ == "__main__":
    main()
