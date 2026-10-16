#!/usr/bin/env python3
"""Append/replace O0 detector scores using ONNX Runtime on det960 tensors."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnxruntime as ort

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.phase0.common.hash_util import sha256_file  # noqa: E402
from experiments.phase0.common.scores_csv import append_scores, make_run_id  # noqa: E402
from experiments.phase0.pc.p3_reference_scores import iter_stems  # noqa: E402


def ort_max_conf(session: ort.InferenceSession, det_uint8_bchw: np.ndarray) -> tuple[float, int]:
    im = det_uint8_bchw.astype(np.float32) / 255.0
    name = session.get_inputs()[0].name
    out = session.run(None, {name: im})[0]
    if out.ndim == 3 and out.shape[1] > 4:
        conf = out[:, 4:, :].reshape(-1)
    else:
        conf = out.reshape(-1)
    conf = conf[np.isfinite(conf)]
    if conf.size == 0:
        return 0.0, 0
    return float(conf.max()), int((conf >= 0.001).sum())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "experiments/phase0/data/tensors",
    )
    args = parser.parse_args()
    onnx_path = REPO_ROOT / "experiments/phase0/engines/onnx/detector.onnx"
    scores_path = REPO_ROOT / "experiments/phase0/results/pc/scores_long.csv"
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    tensor_sha = {}
    with (args.data_dir / "tensor_manifest.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "det960":
                tensor_sha[row["stem"]] = row["sha256"]

    kept: list[dict[str, str]] = []
    with scores_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["cfg"] == "o0" and row["model"] == "det":
                continue
            kept.append(row)

    run_id = make_run_id("o0", "det")
    ts = datetime.now(timezone.utc).isoformat()
    engine_sha = sha256_file(onnx_path)
    new_rows = []
    r0c_det: dict[str, float] = {}
    for row in kept:
        if row["cfg"] == "r0c" and row["model"] == "det" and row["det_max_conf"]:
            r0c_det[row["stem"]] = float(row["det_max_conf"])

    max_diff = 0.0
    for stem, subset, label in iter_stems(REPO_ROOT / "experiments/phase0/results/pc/manifest_images.csv"):
        det = np.load(args.data_dir / f"{stem}_det960.npy")
        max_conf, n_cand = ort_max_conf(session, det)
        ref = r0c_det.get(stem)
        if ref is not None:
            max_diff = max(max_diff, abs(max_conf - ref))
        new_rows.append(
            {
                "run_id": run_id,
                "cfg": "o0",
                "model": "det",
                "build_id": "na",
                "timing_cache": "na",
                "subset": subset,
                "stem": stem,
                "label": label,
                "logit_raw": "",
                "det_max_conf": max_conf,
                "det_n_cand": n_cand,
                "engine_sha256": engine_sha,
                "tensor_sha256": tensor_sha[stem],
                "device": "CPU-ONNX-ORT",
                "ts": ts,
            }
        )

    fieldnames = list(kept[0].keys()) if kept else []
    with scores_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    append_scores(scores_path, new_rows)

    status = "OK" if max_diff <= 1e-3 else "BLOCKED"
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "o0_det_vs_r0c_max_conf_diff": max_diff,
        "status": status,
    }
    out = REPO_ROOT / "experiments/phase0/results/pc/p4_o0_detector_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
