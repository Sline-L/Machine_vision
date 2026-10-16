#!/usr/bin/env python3
"""P1: R0prod reproduction vs val_predictions.csv on val 150."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gp.scratch_v5 import ScratchV5Runtime  # noqa: E402

VAL_PRED = REPO_ROOT / "artifacts/evaluations/scratch-v5/val_predictions.csv"
CONFIG = REPO_ROOT / "model/model2/inference_config.json"
THRESHOLD = 0.300273610279458


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"G:/CODE/gp-dataset/dataset_defects/scratch_v5"),
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=REPO_ROOT / "experiments/phase0/results",
    )
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    results_pc = args.results_root / "pc"
    env_dir = args.results_root / "env"
    results_pc.mkdir(parents=True, exist_ok=True)
    env_dir.mkdir(parents=True, exist_ok=True)

    reference: dict[str, dict[str, str]] = {}
    with VAL_PRED.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            reference[row["stem"]] = row

    val_stems = sorted(reference.keys())
    if len(val_stems) != 150:
        print(f"expected 150 val stems, got {len(val_stems)}", file=sys.stderr)
        return 1

    runtime = ScratchV5Runtime(CONFIG, device=args.device, warmup=True)
    out_path = results_pc / "r0prod_val.csv"
    rows_out: list[dict[str, float | str]] = []
    max_diff = 0.0
    worst: list[tuple[float, str]] = []
    decision_match = 0

    for stem in val_stems:
        image_path = args.dataset_root / "images" / "val" / f"{stem}.jpg"
        crop = cv2.imread(str(image_path))
        if crop is None:
            print(f"BLOCKED: cannot read {image_path}", file=sys.stderr)
            return 1
        pred = runtime.predict(crop)
        fused = float(pred.defect_score)
        ref_prob = float(reference[stem]["scratch_probability"])
        diff = abs(fused - ref_prob)
        max_diff = max(max_diff, diff)
        worst.append((diff, stem))
        ref_dec = reference[stem]["decision"].strip().upper()
        our_dec = "REJECT" if fused >= THRESHOLD else "PASS"
        if our_dec == ref_dec or (ref_dec in {"PASS", "REJECT"} and our_dec == ref_dec):
            decision_match += 1
        elif ref_dec == "FAIL" and our_dec == "REJECT":
            decision_match += 1
        rows_out.append(
            {
                "stem": stem,
                "fused": fused,
                "classifier_prob": float(pred.classifier_probability),
                "detector_prob": float(pred.detector_probability),
            }
        )

    worst.sort(reverse=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["stem", "fused", "classifier_prob", "detector_prob"]
        )
        writer.writeheader()
        writer.writerows(rows_out)

    status = "OK"
    if decision_match != 150 or max_diff > 1e-3:
        status = "BLOCKED"

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n_val": len(val_stems),
        "decision_match": decision_match,
        "max_abs_diff_fused": max_diff,
        "worst_stems": [s for _, s in worst[:5]],
        "worst_diffs": [d for d, _ in worst[:5]],
        "status": status,
    }
    (results_pc / "p1_r0prod_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
