#!/usr/bin/env python3
"""P0: fetch checklist, SHA256 verification, calib split, manifest_images.csv."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.phase0.common.hash_util import sha256_file  # noqa: E402

CALIB_SEED = 2026
CALIB_DEFECT = 42
CALIB_NORMAL = 86
VAL_PRED = REPO_ROOT / "artifacts/evaluations/scratch-v5/val_predictions.csv"


def image_path(dataset_root: Path, split: str, stem: str) -> Path:
    return dataset_root / "images" / split / f"{stem}.jpg"


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_val_predictions() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    with VAL_PRED.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            out[row["stem"]] = row
    return out


def stratified_calib(train_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_label: dict[str, list[dict[str, str]]] = {"scratch": [], "normal": []}
    for row in train_rows:
        label = row["label"]
        if label == "scratch":
            by_label["scratch"].append(row)
        else:
            by_label["normal"].append(row)
    rng = random.Random(CALIB_SEED)
    rng.shuffle(by_label["scratch"])
    rng.shuffle(by_label["normal"])
    picked = by_label["scratch"][:CALIB_DEFECT] + by_label["normal"][:CALIB_NORMAL]
    if len(picked) != CALIB_DEFECT + CALIB_NORMAL:
        raise RuntimeError(
            f"calib sample size mismatch: got {len(picked)}, "
            f"need {CALIB_DEFECT + CALIB_NORMAL}"
        )
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"G:/CODE/gp-dataset/dataset_defects/scratch_v5"),
        help="Local scratch_v5 dataset root (images/ + scratch_manifest.csv)",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=REPO_ROOT / "experiments/phase0/results",
    )
    args = parser.parse_args()
    dataset_root = args.dataset_root.resolve()
    results_pc = args.results_root / "pc"
    results_pc.mkdir(parents=True, exist_ok=True)

    manifest_path = dataset_root / "scratch_manifest.csv"
    cross_path = dataset_root / "cross_split_near_duplicates.csv"
    rows = load_manifest(manifest_path)
    val_preds = load_val_predictions()

    sha_mismatch: list[str] = []
    missing_files: list[str] = []
    file_sha: dict[str, str] = {}
    for row in rows:
        stem = row["stem"]
        split = row["split"]
        path = image_path(dataset_root, split, stem)
        if not path.is_file():
            missing_files.append(stem)
            continue
        digest = sha256_file(path)
        file_sha[stem] = digest
        if digest != row["sha256"]:
            sha_mismatch.append(stem)

    train_rows = [r for r in rows if r["split"] == "train"]
    val_rows = [r for r in rows if r["split"] == "val"]
    calib_rows = stratified_calib(train_rows)
    calib_stems = {r["stem"] for r in calib_rows}
    train_b_rows = [r for r in train_rows if r["stem"] not in calib_stems]

    val_sha = {file_sha[r["stem"]] for r in val_rows if r["stem"] in file_sha}
    train_sha = {file_sha[r["stem"]] for r in train_rows if r["stem"] in file_sha}
    sha_intersection = val_sha & train_sha

    with cross_path.open(encoding="utf-8-sig", newline="") as handle:
        cross_rows = list(csv.DictReader(handle))

    role_map: dict[str, str] = {}
    for r in val_rows:
        role_map[r["stem"]] = "val"
    for r in calib_rows:
        role_map[r["stem"]] = "calib"
    for r in train_b_rows:
        role_map[r["stem"]] = "trainB"

    manifest_out = results_pc / "manifest_images.csv"
    with manifest_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "stem",
                "split",
                "role",
                "label",
                "view",
                "width",
                "height",
                "sha256_file",
                "pc_fused_prob",
            ]
        )
        for row in rows:
            stem = row["stem"]
            role = role_map.get(stem, "")
            view = ""
            fused = ""
            if role == "val" and stem in val_preds:
                view = val_preds[stem].get("view", "")
                fused = val_preds[stem].get("scratch_probability", "")
            label = "scratch" if row["label"] == "scratch" else "normal"
            writer.writerow(
                [
                    stem,
                    row["split"],
                    role,
                    label,
                    view,
                    row["width"],
                    row["height"],
                    file_sha.get(stem, ""),
                    fused,
                ]
            )

    calib_out = results_pc / "calib_manifest.csv"
    with calib_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stem", "label", "sha256_file"])
        for row in calib_rows:
            stem = row["stem"]
            label = "scratch" if row["label"] == "scratch" else "normal"
            writer.writerow([stem, label, file_sha.get(stem, "")])

    calib_labels = Counter("scratch" if r["label"] == "scratch" else "normal" for r in calib_rows)
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n_manifest": len(rows),
        "n_val": len(val_rows),
        "n_calib": len(calib_rows),
        "n_trainB": len(train_b_rows),
        "calib_label_counts": dict(calib_labels),
        "missing_files": len(missing_files),
        "sha_mismatch": len(sha_mismatch),
        "sha_intersection_val_train": len(sha_intersection),
        "cross_split_near_duplicate_rows": max(0, len(cross_rows) - 1) if cross_rows else 0,
        "status": "OK",
    }
    if missing_files or sha_mismatch or len(val_rows) != 150 or len(calib_rows) != 128 or len(train_b_rows) != 236:
        summary["status"] = "BLOCKED"
    if sha_intersection:
        summary["status"] = "BLOCKED"

    summary_path = results_pc / "p0_summary.json"
    import json

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if missing_files[:5]:
        print("missing sample:", missing_files[:5])
    if sha_mismatch[:5]:
        print("sha mismatch sample:", sha_mismatch[:5])
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
