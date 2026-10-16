#!/usr/bin/env python3
"""P3: R0, R0c, R0t reference scores into scores_long.csv."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torchvision.models import efficientnet_b0, resnet18

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.phase0.common.hash_util import sha256_file  # noqa: E402
from experiments.phase0.common.scores_csv import append_scores, make_run_id  # noqa: E402
from experiments.phase0.pc.detector_scores import detector_max_from_tensor  # noqa: E402
from gp.scratch_v5 import load_model2_config  # noqa: E402
from ultralytics import YOLO  # noqa: E402


def load_classifier(path: Path, family: str, device: torch.device):
    try:
        checkpoint = torch.load(str(path), map_location="cpu", weights_only=True)
    except TypeError:
        checkpoint = torch.load(str(path), map_location="cpu")
    state_dict = checkpoint.get("model", checkpoint)
    if family == "efficientnet_b0":
        model = efficientnet_b0(weights=None)
        outputs = int(state_dict["classifier.1.weight"].shape[0])
        model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, outputs)
    else:
        model = resnet18(weights=None)
        outputs = int(state_dict["fc.weight"].shape[0])
        model.fc = torch.nn.Linear(model.fc.in_features, outputs)
    model.load_state_dict(state_dict)
    return model.to(device).eval()


def set_tf32(enabled: bool) -> None:
    torch.backends.cudnn.allow_tf32 = enabled
    torch.backends.cuda.matmul.allow_tf32 = enabled


def set_deterministic(enabled: bool) -> None:
    torch.backends.cudnn.deterministic = enabled
    torch.backends.cudnn.benchmark = not enabled


def iter_stems(manifest_images: Path):
    with manifest_images.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("role"):
                continue
            yield row["stem"], row["role"], row["label"]


def run_cfg(
    cfg: str,
    device_name: str,
    device: torch.device,
    tf32: bool,
    classifiers,
    detector,
    data_dir: Path,
    scores_path: Path,
    tensor_sha: dict[tuple[str, str], str],
) -> None:
    set_tf32(tf32)
    set_deterministic(True)
    run_ids = {
        "c1": make_run_id(cfg, "c1"),
        "c2": make_run_id(cfg, "c2"),
        "det": make_run_id(cfg, "det"),
    }
    ts = datetime.now(timezone.utc).isoformat()
    batch_rows = []
    for stem, subset, label in iter_stems(REPO_ROOT / "experiments/phase0/results/pc/manifest_images.csv"):
        cls_path = data_dir / f"{stem}_cls384.npy"
        det_path = data_dir / f"{stem}_det960.npy"
        cls = np.load(cls_path)
        det = np.load(det_path)
        t_cls = torch.from_numpy(cls).to(device)
        with torch.inference_mode():
            logit1 = float(classifiers[0](t_cls)[0, 0].item())
            logit2 = float(classifiers[1](t_cls)[0, 0].item())
        max_conf, n_cand = detector_max_from_tensor(detector, det, device)
        for model, logit in (("c1", logit1), ("c2", logit2)):
            batch_rows.append(
                {
                    "run_id": run_ids[model],
                    "cfg": cfg,
                    "model": model,
                    "build_id": "na",
                    "timing_cache": "na",
                    "subset": subset,
                    "stem": stem,
                    "label": label,
                    "logit_raw": logit,
                    "det_max_conf": "",
                    "det_n_cand": "",
                    "engine_sha256": "na",
                    "tensor_sha256": tensor_sha[(stem, "cls384")],
                    "device": device_name,
                    "ts": ts,
                }
            )
        batch_rows.append(
            {
                "run_id": run_ids["det"],
                "cfg": cfg,
                "model": "det",
                "build_id": "na",
                "timing_cache": "na",
                "subset": subset,
                "stem": stem,
                "label": label,
                "logit_raw": "",
                "det_max_conf": max_conf,
                "det_n_cand": n_cand,
                "engine_sha256": "na",
                "tensor_sha256": tensor_sha[(stem, "det960")],
                "device": device_name,
                "ts": ts,
            }
        )
    append_scores(scores_path, batch_rows)


def noise_baseline(scores_path: Path) -> dict:
    rows: list[dict[str, str]] = []
    with scores_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_key: dict[tuple[str, str, str], float] = {}
    for row in rows:
        if row["model"] not in {"c1", "c2"} or row["logit_raw"] == "":
            continue
        by_key[(row["stem"], row["model"], row["cfg"])] = float(row["logit_raw"])
    out: dict[str, dict[str, float]] = {}
    for a, b in (("r0c", "r0"), ("r0t", "r0")):
        diffs: list[float] = []
        for (stem, model, cfg), val in list(by_key.items()):
            if cfg != a:
                continue
            other = by_key.get((stem, model, b))
            if other is not None:
                diffs.append(abs(val - other))
        if diffs:
            diffs.sort()
            idx = int(min(len(diffs) - 1, round(0.99 * (len(diffs) - 1))))
            q99 = diffs[idx]
            out[f"{a}_vs_{b}"] = {"max": max(diffs), "q99": q99, "n": len(diffs)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "experiments/phase0/data/tensors",
    )
    args = parser.parse_args()
    config = load_model2_config(REPO_ROOT / "model/model2/inference_config.json", verify_hashes=True)
    c1_cpu = load_classifier(
        config["classifiers"][0]["weights"], config["classifiers"][0]["family"], torch.device("cpu")
    )
    c2_cpu = load_classifier(
        config["classifiers"][1]["weights"], config["classifiers"][1]["family"], torch.device("cpu")
    )
    detector = YOLO(str(config["detector"]["weights"]), task="detect")

    tensor_sha: dict[tuple[str, str], str] = {}
    with (args.data_dir / "tensor_manifest.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            tensor_sha[(row["stem"], row["kind"])] = row["sha256"]

    scores_path = REPO_ROOT / "experiments/phase0/results/pc/scores_long.csv"
    if scores_path.is_file():
        scores_path.unlink()

    gpu = torch.device("cuda:0")
    c1g = load_classifier(
        config["classifiers"][0]["weights"], config["classifiers"][0]["family"], gpu
    )
    c2g = load_classifier(
        config["classifiers"][1]["weights"], config["classifiers"][1]["family"], gpu
    )
    run_cfg("r0", "RTX4060", gpu, False, (c1g, c2g), detector, args.data_dir, scores_path, tensor_sha)
    run_cfg("r0t", "RTX4060-TF32", gpu, True, (c1g, c2g), detector, args.data_dir, scores_path, tensor_sha)
    run_cfg("r0c", "CPU", torch.device("cpu"), False, (c1_cpu, c2_cpu), detector, args.data_dir, scores_path, tensor_sha)

    baseline = noise_baseline(scores_path)
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n_rows": sum(1 for _ in open(scores_path, encoding="utf-8")) - 1,
        "noise_baseline": baseline,
        "status": "OK",
    }
    path = REPO_ROOT / "experiments/phase0/results/pc/p3_summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
