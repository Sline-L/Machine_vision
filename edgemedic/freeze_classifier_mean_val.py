"""Freeze Candidate A (classifier_mean) on Scratch V5 validation only.

Reproduces train_scratch_v5.choose_threshold with PRIMARY_FPR_CAP=0.20.
Does NOT open CLASSIFY_ONLY. Does NOT touch test_scratch.

Usage (NX):

  .venv/bin/python -m edgemedic.freeze_classifier_mean_val \\
    --val-images /path/to/dataset_defects/images/val_scratch \\
    --val-ann /path/to/dataset_defects/annotations/val_scratch \\
    --model2 model/model2/inference_config.json \\
    --out docs/capability-extraction/configs
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from gp.config import PROJECT_ROOT
from gp.scratch_v5 import ScratchV5Runtime, apply_temperature, square_rgb_image

LOCKED_MARKERS = ("test_scratch",)
PRIMARY_FPR_CAP = 0.20
FPR_CAPS = (0.10, 0.20, 0.30, 0.50)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def _refuse_locked(path: Path) -> None:
    text = str(path).replace("\\", "/")
    for marker in LOCKED_MARKERS:
        if marker in text:
            raise SystemExit(f"refusing path that references {marker}: {path}")


def choose_threshold(labels, probabilities, fpr_cap: float):
    """Exact copy of dataset train_scratch_v5.choose_threshold ranking."""
    candidates = sorted({0.0, 1.0, *probabilities})
    best = None
    for threshold in candidates:
        guesses = [value >= threshold for value in probabilities]
        tp = sum(actual == 1 and guess for actual, guess in zip(labels, guesses))
        fp = sum(actual == 0 and guess for actual, guess in zip(labels, guesses))
        tn = sum(actual == 0 and not guess for actual, guess in zip(labels, guesses))
        fn = sum(actual == 1 and not guess for actual, guess in zip(labels, guesses))
        recall = tp / max(1, tp + fn)
        precision = tp / max(1, tp + fp)
        fpr = fp / max(1, fp + tn)
        row = {
            "threshold": float(threshold),
            "recall": recall,
            "precision": precision,
            "f1": 2 * precision * recall / max(1e-9, precision + recall),
            "fpr": fpr,
            "specificity": 1 - fpr,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        }
        key = (fpr <= fpr_cap, recall, -fpr, precision)
        if best is None or key > best[0]:
            best = (key, row)
    assert best is not None
    return best[1], best[0]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_val_samples(image_dir: Path, ann_dir: Path):
    _refuse_locked(image_dir)
    _refuse_locked(ann_dir)
    images = sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    samples = []
    for image_path in images:
        xml_path = ann_dir / f"{image_path.stem}.xml"
        label = 1 if xml_path.is_file() else 0
        samples.append(
            {
                "stem": image_path.stem,
                "path": image_path,
                "label": label,
                "truth": "scratch" if label else "normal",
                "xml": str(xml_path) if xml_path.is_file() else "",
            }
        )
    return samples


def score_classifiers_only(runtime: ScratchV5Runtime, image_bgr):
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    scores = []
    times = []
    with runtime.torch.inference_mode():
        for item, model in runtime.classifiers:
            started = time.perf_counter()
            image = square_rgb_image(rgb, int(item["imgsz"]))
            tensor = runtime.tensor_transform(image).unsqueeze(0).to(runtime.device)
            raw = float(model(tensor).sigmoid()[0, 0].item())
            times.append((time.perf_counter() - started) * 1000)
            scores.append(apply_temperature(raw, item.get("temperature", 1.0)))
    mean_score = float(np.mean(scores))
    return scores[0], scores[1], mean_score, times


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--val-images", type=Path, required=True)
    parser.add_argument("--val-ann", type=Path, required=True)
    parser.add_argument(
        "--model2",
        type=Path,
        default=PROJECT_ROOT / "model" / "model2" / "inference_config.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "docs" / "capability-extraction" / "configs",
    )
    parser.add_argument(
        "--selection-rule-doc",
        type=Path,
        default=PROJECT_ROOT
        / "docs"
        / "capability-extraction"
        / "selection-rule-candidate-a.md",
    )
    parser.add_argument("--dataset-commit", default="")
    args = parser.parse_args(argv)

    _refuse_locked(args.val_images)
    _refuse_locked(args.val_ann)
    _refuse_locked(args.out)
    if not args.selection_rule_doc.is_file():
        raise SystemExit("selection rule doc missing; refuse to compute threshold without it")

    samples = load_val_samples(args.val_images.resolve(), args.val_ann.resolve())
    if len(samples) != 150:
        raise SystemExit(f"expected 150 val_scratch images, got {len(samples)}")
    n_scratch = sum(s["label"] for s in samples)
    n_normal = len(samples) - n_scratch
    if n_scratch != 43 or n_normal != 107:
        raise SystemExit(
            f"expected 43 scratch / 107 normal, got {n_scratch} / {n_normal}"
        )

    runtime = ScratchV5Runtime(args.model2, warmup=True)
    # Warmup loads detector; inference below never calls it.
    rows = []
    labels = []
    probabilities = []
    for sample in samples:
        image = cv2.imread(str(sample["path"]))
        if image is None:
            raise SystemExit(f"failed to read {sample['path']}")
        c1, c2, mean_score, times = score_classifiers_only(runtime, image)
        labels.append(sample["label"])
        probabilities.append(mean_score)
        rows.append(
            {
                "stem": sample["stem"],
                "truth": sample["truth"],
                "label": sample["label"],
                "classifier_1": c1,
                "classifier_2": c2,
                "classifier_mean": mean_score,
                "classifier1_ms": times[0] if times else 0.0,
                "classifier2_ms": times[1] if len(times) > 1 else 0.0,
                "image_sha256": file_sha256(sample["path"]),
            }
        )

    primary, primary_key = choose_threshold(labels, probabilities, PRIMARY_FPR_CAP)
    operating_points = {}
    for cap in FPR_CAPS:
        point, key = choose_threshold(labels, probabilities, cap)
        operating_points[str(cap)] = {
            **point,
            "selection_key": [bool(key[0]), key[1], key[2], key[3]],
        }

    target_met = (
        float(primary["recall"]) >= 0.95 and float(primary["fpr"]) <= PRIMARY_FPR_CAP
    )
    threshold = float(primary["threshold"])
    for row in rows:
        decision = "REJECT" if row["classifier_mean"] >= threshold else "PASS"
        row["threshold"] = threshold
        row["decision"] = decision
        row["correct"] = int(
            (decision == "REJECT" and row["label"] == 1)
            or (decision == "PASS" and row["label"] == 0)
        )

    classifiers = runtime.config["classifiers"]
    artifact_hashes = {
        Path(item["weights"]).name: {
            "name": item["name"],
            "sha256": item.get("sha256") or file_sha256(Path(item["weights"])),
            "imgsz": item["imgsz"],
            "temperature": item["temperature"],
            "family": item["family"],
        }
        for item in classifiers
    }

    frozen_config = {
        "version": "scratch_v5",
        "profile_candidate": "A_classifier_mean_both",
        "profile_id": "classifier_only_mean_v1",
        "classes": {"0": "normal", "1": "scratch"},
        "classifiers": [
            {
                "name": item["name"],
                "family": item["family"],
                "weights": Path(item["weights"]).name,
                "sha256": artifact_hashes[Path(item["weights"]).name]["sha256"],
                "imgsz": item["imgsz"],
                "tta": item.get("tta", "none"),
                "temperature": item["temperature"],
            }
            for item in classifiers
        ],
        "detector": None,
        "fusion": {
            "type": "classifier_mean",
            "models": [item["name"] for item in classifiers],
        },
        "default_threshold": threshold,
        "operating_points": operating_points,
        "decision": "REJECT when scratch probability >= threshold",
        "validation": {
            "split": "val_scratch",
            "n_images": len(samples),
            "n_scratch": n_scratch,
            "n_normal": n_normal,
            "primary_fpr_cap": PRIMARY_FPR_CAP,
            **primary,
            "target": {"scratch_recall": 0.95, "normal_fpr_max": PRIMARY_FPR_CAP},
            "target_met": target_met,
            "blind": False,
            "notes": "val participated in threshold selection; not a locked-test claim",
        },
        "selection_rule": {
            "source": "train_scratch_v5.choose_threshold",
            "documented_in": str(args.selection_rule_doc.as_posix()),
            "primary_fpr_cap": PRIMARY_FPR_CAP,
            "key": "(fpr <= primary_fpr_cap, recall, -fpr, precision)",
            "chosen_key": [
                bool(primary_key[0]),
                primary_key[1],
                primary_key[2],
                primary_key[3],
            ],
            "temperatures_refit": False,
        },
        "provenance": {
            "freeze_id": f"classifier_only_mean_v1_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "freeze_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model2_config": str(Path(args.model2).resolve()),
            "model2_config_sha256": file_sha256(Path(args.model2)),
            "val_images": str(Path(args.val_images).resolve()),
            "val_annotations": str(Path(args.val_ann).resolve()),
            "dataset_commit": args.dataset_commit or None,
            "artifact_hashes": artifact_hashes,
            "test_scratch_accessed": False,
            "classify_only_api_opened": False,
        },
        "locked_test": None,
        "notes": [
            "Step 2 freeze only. Do not retune on test_scratch.",
            "Do not open GearPro CLASSIFY_ONLY from this file alone.",
        ],
    }

    raw = json.dumps(frozen_config, sort_keys=True, separators=(",", ":"))
    frozen_config["config_hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frozen_path = out / "classifier_only_mean.val-frozen.json"
    frozen_path.write_text(json.dumps(frozen_config, indent=2), encoding="utf-8")

    pred_path = out / "classifier_only_mean.val_predictions.csv"
    with pred_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    trace = {
        "selection_rule_doc": str(args.selection_rule_doc),
        "primary_operating_point": primary,
        "primary_key": [
            bool(primary_key[0]),
            primary_key[1],
            primary_key[2],
            primary_key[3],
        ],
        "target_met": target_met,
        "score_summary": {
            "min": min(probabilities),
            "max": max(probabilities),
            "mean": float(np.mean(probabilities)),
        },
        "confusion": {
            "tp": primary["tp"],
            "fp": primary["fp"],
            "tn": primary["tn"],
            "fn": primary["fn"],
        },
        "n_images": len(samples),
        "test_scratch_accessed": False,
    }
    (out / "classifier_only_mean.selection_trace.json").write_text(
        json.dumps(trace, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "frozen": str(frozen_path),
                "threshold": threshold,
                "recall": primary["recall"],
                "fpr": primary["fpr"],
                "precision": primary["precision"],
                "f1": primary["f1"],
                "target_met": target_met,
                "config_hash": frozen_config["config_hash"],
                "test_scratch_accessed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
