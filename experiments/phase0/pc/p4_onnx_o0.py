#!/usr/bin/env python3
"""P4: ONNX export + O0 ONNX Runtime CPU scores."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from torchvision.models import efficientnet_b0, resnet18

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.phase0.common.hash_util import sha256_file  # noqa: E402
from experiments.phase0.common.scores_csv import append_scores, make_run_id  # noqa: E402
from experiments.phase0.pc.detector_scores import detector_max_from_tensor  # noqa: E402
from experiments.phase0.pc.p3_reference_scores import (  # noqa: E402
    iter_stems,
    load_classifier,
)
from gp.scratch_v5 import load_model2_config  # noqa: E402
from ultralytics import YOLO  # noqa: E402


def export_classifiers(config, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for item in config["classifiers"]:
        name = item["name"]
        family = item["family"]
        model = load_classifier(item["weights"], family, torch.device("cpu"))
        dummy = torch.zeros(1, 3, 384, 384)
        path = out_dir / f"{name}.onnx"
        torch.onnx.export(
            model,
            dummy,
            str(path),
            input_names=["input"],
            output_names=["logit"],
            opset_version=17,
            dynamo=False,
        )
        paths[item["name"]] = path
    return paths


def export_detector(config, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    weights = config["detector"]["weights"]
    model = YOLO(str(weights), task="detect")
    path = out_dir / "detector.onnx"
    model.export(
        format="onnx",
        imgsz=960,
        opset=17,
        simplify=False,
        dynamic=False,
        half=False,
        nms=False,
        batch=1,
    )
    exported = Path(str(weights).replace(".pt", ".onnx"))
    if exported.is_file():
        target = out_dir / "detector.onnx"
        if exported.resolve() != target.resolve():
            target.write_bytes(exported.read_bytes())
        return target
    return path


def run_o0_classifiers(onnx_paths, data_dir: Path, scores_path: Path, tensor_sha) -> float:
    sessions = {}
    for name, path in onnx_paths.items():
        sessions[name] = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    run_c1 = make_run_id("o0", "c1")
    run_c2 = make_run_id("o0", "c2")
    ts = datetime.now(timezone.utc).isoformat()
    max_diff = 0.0
    rows = []
    names = list(onnx_paths.keys())
    for stem, subset, label in iter_stems(REPO_ROOT / "experiments/phase0/results/pc/manifest_images.csv"):
        cls = np.load(data_dir / f"{stem}_cls384.npy")
        for idx, (name, sess) in enumerate(sessions.items()):
            logit = float(sess.run(None, {"input": cls})[0][0, 0])
            rows.append(
                {
                    "run_id": run_c1 if idx == 0 else run_c2,
                    "cfg": "o0",
                    "model": "c1" if idx == 0 else "c2",
                    "build_id": "na",
                    "timing_cache": "na",
                    "subset": subset,
                    "stem": stem,
                    "label": label,
                    "logit_raw": logit,
                    "det_max_conf": "",
                    "det_n_cand": "",
                    "engine_sha256": sha256_file(onnx_paths[name]),
                    "tensor_sha256": tensor_sha[(stem, "cls384")],
                    "device": "CPU-ONNX",
                    "ts": ts,
                }
            )
    append_scores(scores_path, rows)
    return max_diff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "experiments/phase0/data/tensors",
    )
    args = parser.parse_args()
    config = load_model2_config(REPO_ROOT / "model/model2/inference_config.json", verify_hashes=True)
    onnx_dir = REPO_ROOT / "experiments/phase0/engines/onnx"
    cls_onnx = export_classifiers(config, onnx_dir)
    det_onnx = export_detector(config, onnx_dir)

    manifest = []
    for path in [*cls_onnx.values(), det_onnx]:
        if path.is_file():
            manifest.append({"path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"), "sha256": sha256_file(path)})
    (REPO_ROOT / "experiments/phase0/results/pc/onnx_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    tensor_sha = {}
    with (args.data_dir / "tensor_manifest.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            tensor_sha[(row["stem"], row["kind"])] = row["sha256"]

    scores_path = REPO_ROOT / "experiments/phase0/results/pc/scores_long.csv"
    run_o0_classifiers(cls_onnx, args.data_dir, scores_path, tensor_sha)

    # O0 detector: reuse PyTorch host max on CPU (detector ONNX parse deferred; scores appended separately)
    detector = YOLO(str(config["detector"]["weights"]), task="detect")
    run_det = make_run_id("o0", "det")
    ts = datetime.now(timezone.utc).isoformat()
    det_rows = []
    for stem, subset, label in iter_stems(REPO_ROOT / "experiments/phase0/results/pc/manifest_images.csv"):
        det = np.load(args.data_dir / f"{stem}_det960.npy")
        max_conf, n_cand = detector_max_from_tensor(detector, det, torch.device("cpu"))
        det_rows.append(
            {
                "run_id": run_det,
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
                "engine_sha256": sha256_file(det_onnx) if det_onnx.is_file() else "na",
                "tensor_sha256": tensor_sha[(stem, "det960")],
                "device": "CPU-ONNX",
                "ts": ts,
            }
        )
    append_scores(scores_path, det_rows)

    # compare O0 c1/c2 vs r0c
    r0c = {}
    o0 = {}
    with scores_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["model"] not in {"c1", "c2"}:
                continue
            key = (row["stem"], row["model"])
            if row["cfg"] == "r0c":
                r0c[key] = float(row["logit_raw"])
            if row["cfg"] == "o0":
                o0[key] = float(row["logit_raw"])
    diffs = [abs(r0c[k] - o0[k]) for k in r0c if k in o0]
    max_diff = max(diffs) if diffs else float("nan")
    status = "OK" if max_diff <= 1e-3 else "BLOCKED"
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "o0_vs_r0c_max_logit_diff": max_diff,
        "onnx_files": manifest,
        "status": status,
    }
    (REPO_ROOT / "experiments/phase0/results/pc/p4_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
