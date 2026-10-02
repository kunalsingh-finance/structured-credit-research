"""Run the supplemental study without altering primary research outputs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from credit_research.credit_models import load_panel, train_credit_models
from credit_research.extended_validation import FOLD_WINDOWS, SEGMENTS, run_extended_validation


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=str(ROOT / "data/loan_panel.sqlite"))
    parser.add_argument("--output", default=str(ROOT / "output/extended_validation.json"))
    args = parser.parse_args()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((ROOT / "configs/supplemental_validation_protocol.json").read_text(encoding="utf-8"))
    if (protocol["expanding_folds"] != [list(w) for w in FOLD_WINDOWS]
            or protocol["cohort_smoothing_pseudo_observations"] != 100
            or protocol["segment_features"] != list(SEGMENTS)):
        raise ValueError("Supplemental protocol differs from independently encoded fixed study")
    identity = {"panel_sha256": sha256(args.panel),
                "primary_protocol_sha256": sha256(ROOT / "configs/research_protocol.json"),
                "credit_model_code_sha256": sha256(ROOT / "credit_research/credit_models.py"),
                "extended_validation_code_sha256": sha256(ROOT / "credit_research/extended_validation.py"),
                "runner_code_sha256": sha256(Path(__file__)),
                "supplemental_protocol_sha256": sha256(ROOT / "configs/supplemental_validation_protocol.json")}
    started = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps({"status": "BUILDING", "started_at": started, "build_identity": identity}), encoding="utf-8")
    try:
        print("Loading actual panel; refitting unchanged primary specification for segment probabilities", flush=True)
        panel = load_panel(args.panel)
        primary, predict = train_credit_models(panel)
        result = run_extended_validation(panel, predict, progress=lambda s: print(s, flush=True))
        result.update(generated_at=datetime.now(timezone.utc).isoformat(), started_at=started,
                      build_identity=identity, panel_rows=len(panel),
                      supplemental_protocol=protocol,
                      primary_refit={"method": primary["method"], "splits": primary["splits"],
                                     "purpose": "Reproduce unchanged primary predictions for fixed-segment diagnostics; no primary outputs overwritten"})
        if not all(result["checks"].values()):
            raise AssertionError("Supplemental validation control failed")
        path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), "status": result["status"], "folds": len(result["expanding_folds"]),
                          "checks": result["checks"]}, indent=2), flush=True)
    except Exception as error:
        path.write_text(json.dumps({"status": "FAILED", "started_at": started,
                                   "build_identity": identity, "error": str(error)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
