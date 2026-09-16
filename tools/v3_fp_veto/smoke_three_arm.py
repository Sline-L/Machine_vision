#!/usr/bin/env python3
"""Non-holdout live three-arm smoke test (train/val images only).

Integration test, not model evaluation. Refuses test_scratch / holdout / fresh.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from v3_fp_veto.frozen_inference import (  # noqa: E402
    CANDIDATE_COMMIT,
    EXPECTED_FEATURE_NAMES,
    V3_1_THRESHOLD,
    backbone_features,
    load_frozen_veto,
    load_full_threshold,
    load_v2_threshold,
    score_full,
    score_v2,
    score_v3_1,
)

FORBIDDEN = ("test_scratch", "holdout", "fresh")
DEFAULT_IMAGES = Path(r"G:/CODE/Machine_vision_dataset_audit/dataset_defects/images")
DEFAULT_ANNS = Path(r"G:/CODE/Machine_vision_dataset_audit/dataset_defects/annotations")
TRAIN_MANIFEST = ROOT / "docs/capability-extraction/v3/v3-1-engineering-freeze/manifest_train_scratch.csv"
VAL_MANIFEST = ROOT / "docs/capability-extraction/v3/v3-1-engineering-freeze/manifest_val_scratch.csv"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _refuse_path(path: Path) -> None:
    text = str(path).replace("\\", "/").lower()
    for token in FORBIDDEN:
        if token in text:
            raise SystemExit(f"REFUSE: path contains {token}: {path}")


def _read_manifest(path: Path, split: str, n: int) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    picked = []
    for row in rows:
        picked.append({"split": split, **row})
        if len(picked) >= n:
            break
    return picked


def _xml_label(ann_root: Path, stem: str) -> int:
    xml_path = ann_root / f"{stem}.xml"
    if not xml_path.is_file():
        return 0
    root = ET.parse(xml_path).getroot()
    return 1 if root.findall("object") else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Live three-arm smoke test on train/val only")
    parser.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--ann-root", type=Path, default=DEFAULT_ANNS)
    parser.add_argument("--n-train", type=int, default=2)
    parser.add_argument("--n-val", type=int, default=2)
    parser.add_argument("--device", default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "docs/capability-extraction/v3/v3-1-adjudication-tooling/live-smoke-train-val",
    )
    args = parser.parse_args(argv)
    _refuse_path(args.images_root)
    _refuse_path(args.ann_root)
    _refuse_path(args.out_dir)

    import cv2
    from gp.capability_v2 import FULL_INFERENCE_CONFIG, V2_INFERENCE_CONFIG, validate_frozen_artifacts
    from gp.scratch_v5 import ScratchV5Runtime

    validate_frozen_artifacts()
    v2_thr = load_v2_threshold()
    full_thr = load_full_threshold()
    if abs(v2_thr - 0.2653394325872992) > 1e-12:
        raise SystemExit(f"V2 threshold mismatch: {v2_thr}")
    if abs(full_thr - 0.300273610279458) > 1e-12:
        raise SystemExit(f"FULL threshold mismatch: {full_thr}")
    veto = load_frozen_veto()
    if abs(veto.threshold - V3_1_THRESHOLD) > 1e-12:
        raise SystemExit("V3-1 threshold mismatch")

    selected = _read_manifest(TRAIN_MANIFEST, "train_scratch", args.n_train)
    selected += _read_manifest(VAL_MANIFEST, "val_scratch", args.n_val)
    runtime_full = ScratchV5Runtime(FULL_INFERENCE_CONFIG, device=args.device, warmup=True)
    runtime_v2 = ScratchV5Runtime(V2_INFERENCE_CONFIG, device=args.device, warmup=True)

    rows_out = []
    schema_ok = True
    notes = []
    for item in selected:
        split = item["split"]
        name = item["image"]
        path = args.images_root / split / name
        _refuse_path(path)
        if not path.is_file():
            raise SystemExit(f"missing image {path}")
        listed = item.get("sha256")
        actual = _sha256_file(path)
        if listed and listed != actual:
            raise SystemExit(f"sha mismatch {name}")
        crop = cv2.imread(str(path))
        if crop is None:
            raise SystemExit(f"read fail {path}")
        gt = int(item["label"])
        xml_gt = _xml_label(args.ann_root / split, path.stem)
        if xml_gt != gt:
            notes.append(f"xml/manifest label differ {name}: xml={xml_gt} manifest={gt}")
        full = score_full(runtime_full, crop, threshold=full_thr)
        v2 = score_v2(runtime_v2, crop, threshold=v2_thr)
        v31 = score_v3_1(runtime_v2, crop, veto, v2_threshold=v2_thr)
        feat = v31["features"]
        order_ok = list(veto.feature_names) == EXPECTED_FEATURE_NAMES
        fused_vs_predict = abs(float(feat["fused_v2"]) - float(v2["score"]))
        replace = int(float(v31["veto_probability"]) >= V3_1_THRESHOLD)
        if int(v31["prediction"]) != replace:
            schema_ok = False
            notes.append(f"{name}: V3-1 prediction != (p >= 0.845)")
        if fused_vs_predict > 1e-6:
            notes.append(f"{name}: V2 predict vs backbone fused delta={fused_vs_predict}")
        rows_out.append(
            {
                "sample_id": name,
                "split": split,
                "ground_truth": gt,
                "full_score": full["score"],
                "full_threshold": full["threshold"],
                "full_prediction": full["prediction"],
                "v2_score": v2["score"],
                "v2_threshold": v2["threshold"],
                "v2_prediction": v2["prediction"],
                "v3_1_feature_names": list(veto.feature_names),
                "v3_1_feature_vector": v31["feature_vector"],
                "v3_1_score": v31["score"],
                "v3_1_threshold": v31["threshold"],
                "v3_1_prediction": v31["prediction"],
                "veto_probability": v31["veto_probability"],
                "veto_triggered": v31["veto_triggered"],
                "replace_score_equals_p_ge_0845": int(v31["prediction"]) == replace,
                "v2_fused_vs_predict_abs_delta": fused_vs_predict,
                "feature_order_ok": order_ok,
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "sample_id",
        "split",
        "ground_truth",
        "full_score",
        "full_threshold",
        "full_prediction",
        "v2_score",
        "v2_threshold",
        "v2_prediction",
        "v3_1_score",
        "v3_1_threshold",
        "v3_1_prediction",
        "veto_probability",
        "veto_triggered",
    ]
    with (args.out_dir / "per_sample.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)
    report = {
        "banner": "V3-1 LIVE THREE-ARM SMOKE — TRAIN/VAL ONLY — NOT HOLDOUT — NOT VALIDATION",
        "candidate_commit": CANDIDATE_COMMIT,
        "adjudicator_commit": _git_head(),
        "fresh_holdout": "UNTOUCHED",
        "purpose": "integration smoke; no development metrics",
        "replace_score_semantics": (
            "Mode A: logistic p replaces V2 fused score entirely; "
            "prediction = (p >= 0.845). Not Mode B v2_reject AND p."
        ),
        "thresholds": {
            "FULL": full_thr,
            "V2": v2_thr,
            "V3-1": V3_1_THRESHOLD,
        },
        "n": len(rows_out),
        "samples": rows_out,
        "schema_ok": schema_ok and all(r["replace_score_equals_p_ge_0845"] for r in rows_out),
        "notes": notes,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"n": report["n"], "schema_ok": report["schema_ok"], "out": str(args.out_dir)}, indent=2))
    return 0 if report["schema_ok"] else 2


def _git_head() -> str:
    import subprocess

    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(main())
