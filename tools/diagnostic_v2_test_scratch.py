#!/usr/bin/env python3
"""DIAGNOSTIC ONLY — frozen V2 vs FULL on consumed test_scratch.

THIS DATASET IS ALREADY CONSUMED.
THIS RESULT MUST NOT BE USED FOR FORMAL CAPABILITY ADMISSION.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

BANNER = (
    "DIAGNOSTIC ONLY\n"
    "THIS DATASET IS ALREADY CONSUMED.\n"
    "THIS RESULT MUST NOT BE USED FOR FORMAL CAPABILITY ADMISSION."
)

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_labels(images: Path, annotations: Path):
    paths = sorted(p for p in images.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    labels = []
    for path in paths:
        xml_path = annotations / f"{path.stem}.xml"
        if not xml_path.is_file():
            labels.append(0)
            continue
        root = ET.parse(xml_path).getroot()
        objects = root.findall("object")
        labels.append(1 if objects else 0)
    return paths, labels


def metrics_from_counts(tp, fp, tn, fn):
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    specificity = 1.0 - fpr
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    q_d = min(recall, specificity)
    u = 0.5 + 0.5 * q_d
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "n": tp + fp + tn + fn,
        "recall": recall,
        "fpr": fpr,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "Q_D": q_d,
        "U": u,
        "dataset_target_recall_0_95": recall >= 0.95,
        "dataset_target_fpr_max_0_20": fpr <= 0.2,
        "edgemedic_q_d_floor_0_70": q_d >= 0.70,
    }


def predict_components(runtime, crop):
    """Return fused prediction plus per-classifier scores (diagnostic)."""
    from gp.scratch_v5 import apply_temperature, fuse_probabilities, fuse_single_classifier, square_rgb_image

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    classifier_scores = []
    with runtime.torch.inference_mode():
        for item, model in runtime.classifiers:
            image = square_rgb_image(rgb, int(item["imgsz"]))
            tensor = runtime.tensor_transform(image).unsqueeze(0).to(runtime.device)
            raw = float(model(tensor).sigmoid()[0, 0].item())
            classifier_scores.append(apply_temperature(raw, item.get("temperature", 1.0)))

    detector = runtime.config["detector"]
    result = runtime.detector.predict(
        crop,
        imgsz=int(detector["imgsz"]),
        conf=float(detector["conf_floor"]),
        iou=float(detector["iou"]),
        device=runtime.yolo_device,
        verbose=False,
    )[0]
    raw_detector = 0.0
    if result.boxes is not None and len(result.boxes):
        confidences = result.boxes.conf.detach().cpu().numpy()
        raw_detector = float(np.max(confidences))
    detector_score = apply_temperature(raw_detector, detector.get("temperature", 1.0))
    alpha = runtime.config["fusion"]["alpha"]
    if len(classifier_scores) == 1:
        fused, classifier_score = fuse_single_classifier(classifier_scores[0], detector_score, alpha)
        cls2 = None
    else:
        fused, classifier_score = fuse_probabilities(
            classifier_scores[0], classifier_scores[1], detector_score, alpha
        )
        cls2 = classifier_scores[1]
    threshold = float(runtime.config["default_threshold"])
    reject = fused >= threshold
    return {
        "fused": fused,
        "classifier_fused": classifier_score,
        "cls1": classifier_scores[0],
        "cls2": cls2,
        "detector": detector_score,
        "threshold": threshold,
        "reject": bool(reject),
    }


def evaluate_profile(runtime, paths, labels, profile_name: str):
    rows = []
    tp = fp = tn = fn = 0
    for path, label in zip(paths, labels):
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"failed to read {path}")
        # Gear ROI = full image for test_scratch (same as teammate evaluator using whole image)
        pred = predict_components(runtime, image)
        y_hat = 1 if pred["reject"] else 0
        if label == 1 and y_hat == 1:
            tp += 1
            outcome = "TP"
        elif label == 0 and y_hat == 1:
            fp += 1
            outcome = "FP"
        elif label == 0 and y_hat == 0:
            tn += 1
            outcome = "TN"
        else:
            fn += 1
            outcome = "FN"
        rows.append(
            {
                "image": path.name,
                "label": int(label),
                "profile": profile_name,
                "verdict": "REJECT" if y_hat else "PASS",
                "outcome": outcome,
                **pred,
            }
        )
    return rows, metrics_from_counts(tp, fp, tn, fn)


def disagreement(full_rows, v2_rows):
    by_img = {r["image"]: r for r in full_rows}
    out = []
    counts = {
        "both_correct": 0,
        "full_correct_v2_wrong": 0,
        "full_wrong_v2_correct": 0,
        "both_wrong": 0,
        "pos_full_correct_v2_wrong": 0,
        "neg_full_correct_v2_wrong": 0,
        "resnet_changed_verdict": 0,
        "resnet_rescues_fn": 0,
        "resnet_suppresses_fp": 0,
    }
    for v2 in v2_rows:
        full = by_img[v2["image"]]
        full_ok = full["outcome"] in {"TP", "TN"}
        v2_ok = v2["outcome"] in {"TP", "TN"}
        if full_ok and v2_ok:
            klass = "FULL_correct_V2_correct"
            counts["both_correct"] += 1
        elif full_ok and not v2_ok:
            klass = "FULL_correct_V2_wrong"
            counts["full_correct_v2_wrong"] += 1
            if full["label"] == 1:
                counts["pos_full_correct_v2_wrong"] += 1
            else:
                counts["neg_full_correct_v2_wrong"] += 1
        elif (not full_ok) and v2_ok:
            klass = "FULL_wrong_V2_correct"
            counts["full_wrong_v2_correct"] += 1
        else:
            klass = "FULL_wrong_V2_wrong"
            counts["both_wrong"] += 1

        # ResNet effect: compare FULL reject vs hypothetic EffNet-only using FULL cls1+det
        # Approximate with actual FULL vs V2 verdicts when topologies differ only by cls2.
        if full["verdict"] != v2["verdict"]:
            counts["resnet_changed_verdict"] += 1
            if full["label"] == 1 and full["verdict"] == "REJECT" and v2["verdict"] == "PASS":
                counts["resnet_rescues_fn"] += 1
            if full["label"] == 0 and full["verdict"] == "PASS" and v2["verdict"] == "REJECT":
                counts["resnet_suppresses_fp"] += 1

        out.append(
            {
                "image": v2["image"],
                "label": full["label"],
                "FULL_verdict": full["verdict"],
                "FULL_fused": full["fused"],
                "FULL_cls1": full["cls1"],
                "FULL_cls2": full["cls2"],
                "FULL_detector": full["detector"],
                "FULL_threshold": full["threshold"],
                "V2_verdict": v2["verdict"],
                "V2_fused": v2["fused"],
                "V2_cls1": v2["cls1"],
                "V2_detector": v2["detector"],
                "V2_threshold": v2["threshold"],
                "classification": klass,
            }
        )
    return out, counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--images",
        type=Path,
        default=Path(r"G:/CODE/Machine_vision_dataset_audit/dataset_defects/images/test_scratch"),
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path(r"G:/CODE/Machine_vision_dataset_audit/dataset_defects/annotations/test_scratch"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/capability-extraction/v3/diagnostic-test_scratch-v2"),
    )
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    print(BANNER, flush=True)
    root = Path(__file__).resolve().parents[1]
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    from gp.capability_v2 import (
        FULL_INFERENCE_CONFIG,
        V2_INFERENCE_CONFIG,
        load_frozen,
        validate_frozen_artifacts,
    )
    from gp.scratch_v5 import ScratchV5Runtime

    frozen = load_frozen()
    validate_frozen_artifacts()
    identity = {
        "frozen_config_hash": frozen["config_hash"],
        "frozen_threshold": frozen["threshold"],
        "frozen_classifier_sha": frozen["classifier"]["sha256"],
        "frozen_detector_sha": frozen["detector"]["sha256"],
        "frozen_fusion_alpha": frozen["fusion"]["alpha"],
        "full_config": str(FULL_INFERENCE_CONFIG),
        "v2_config": str(V2_INFERENCE_CONFIG),
    }
    # Prove artifact SHAs on disk
    full_cfg = json.loads(Path(FULL_INFERENCE_CONFIG).read_text(encoding="utf-8"))
    v2_cfg = json.loads(Path(V2_INFERENCE_CONFIG).read_text(encoding="utf-8"))
    model_dir = Path(FULL_INFERENCE_CONFIG).parent
    identity["full_cls1_sha_disk"] = sha256_file(model_dir / full_cfg["classifiers"][0]["weights"])
    identity["full_cls2_sha_disk"] = sha256_file(model_dir / full_cfg["classifiers"][1]["weights"])
    identity["full_det_sha_disk"] = sha256_file(model_dir / full_cfg["detector"]["weights"])
    identity["v2_cls1_sha_disk"] = sha256_file(
        Path(V2_INFERENCE_CONFIG).parent / v2_cfg["classifiers"][0]["weights"]
        if not Path(v2_cfg["classifiers"][0]["weights"]).is_absolute()
        else Path(v2_cfg["classifiers"][0]["weights"])
    )
    # V2 weights may be relative to profile dir or model2
    v2_cls_path = Path(v2_cfg["classifiers"][0]["weights"])
    if not v2_cls_path.is_file():
        v2_cls_path = Path(V2_INFERENCE_CONFIG).parent / v2_cfg["classifiers"][0]["weights"]
    if not v2_cls_path.is_file():
        v2_cls_path = model_dir / Path(v2_cfg["classifiers"][0]["weights"]).name
    identity["v2_cls1_sha_disk"] = sha256_file(v2_cls_path)
    identity["sha_match_effnet"] = identity["v2_cls1_sha_disk"].lower() == frozen["classifier"]["sha256"].lower()
    identity["sha_match_detector"] = identity["full_det_sha_disk"].lower() == frozen["detector"]["sha256"].lower()
    identity["threshold_unchanged"] = abs(float(v2_cfg["default_threshold"]) - float(frozen["threshold"])) < 1e-12

    paths, labels = load_labels(args.images, args.annotations)
    print(f"n_images={len(paths)} positives={sum(labels)}", flush=True)

    print("loading FULL...", flush=True)
    full_rt = ScratchV5Runtime(FULL_INFERENCE_CONFIG, device=args.device, warmup=True)
    full_rows, full_metrics = evaluate_profile(full_rt, paths, labels, "FULL")
    del full_rt

    print("loading V2...", flush=True)
    v2_rt = ScratchV5Runtime(V2_INFERENCE_CONFIG, device=args.device, warmup=True)
    v2_rows, v2_metrics = evaluate_profile(v2_rt, paths, labels, "LATENCY_DEGRADED_V2")
    del v2_rt

    pairs, counts = disagreement(full_rows, v2_rows)
    delta = {k: v2_metrics[k] - full_metrics[k] for k in ("recall", "fpr", "specificity", "precision", "f1", "Q_D", "U")}

    # FULL val gap note from frozen / known
    report = {
        "banner": BANNER,
        "mode": "DIAGNOSTIC ONLY",
        "fresh_holdout": False,
        "test_scratch": "CONSUMED",
        "consumption_reasons": [
            "classifier_only_v1 formal/diagnostic use",
            "FULL Scratch V5 teammate locked evaluation",
        ],
        "mission_approved": False,
        "admission_proposal": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "identity": identity,
        "FULL": full_metrics,
        "LATENCY_DEGRADED_V2": v2_metrics,
        "delta_v2_minus_full": delta,
        "disagreement_counts": counts,
        "full_generalization_gap_note": {
            "val_Q_D_approx": 0.916,
            "locked_test_Q_D": full_metrics["Q_D"],
            "note": "FULL itself has nontrivial validation → locked-domain gap; do not retune FULL threshold",
        },
        "gates": {
            "dataset_target": {
                "scratch_recall_ge_0_95": {
                    "FULL": full_metrics["dataset_target_recall_0_95"],
                    "V2": v2_metrics["dataset_target_recall_0_95"],
                },
                "normal_fpr_le_0_20": {
                    "FULL": full_metrics["dataset_target_fpr_max_0_20"],
                    "V2": v2_metrics["dataset_target_fpr_max_0_20"],
                },
            },
            "edgemedic_mission_contract": {
                "Q_D_ge_0_70_assuming_QL_QS_1": {
                    "FULL": full_metrics["edgemedic_q_d_floor_0_70"],
                    "V2": v2_metrics["edgemedic_q_d_floor_0_70"],
                }
            },
        },
        "quality_conclusion": None,
    }

    qd_delta = delta["Q_D"]
    if qd_delta >= -0.03:
        report["quality_conclusion"] = (
            "DIAGNOSTIC EVIDENCE: V2 quality loss relative to FULL appears limited "
            "on the already-consumed test_scratch."
        )
    else:
        report["quality_conclusion"] = (
            "V2 HAS MATERIAL QUALITY RISK ON CONSUMED DIAGNOSTIC TEST "
            "(future V3 design evidence; do not retune V2)."
        )

    # Write artifacts
    (out_dir / "README.md").write_text(BANNER + "\n", encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    with (out_dir / "full_predictions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(full_rows[0].keys()))
        w.writeheader()
        w.writerows(full_rows)
    with (out_dir / "v2_predictions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(v2_rows[0].keys()))
        w.writeheader()
        w.writerows(v2_rows)
    with (out_dir / "paired_disagreements.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pairs[0].keys()))
        w.writeheader()
        w.writerows(pairs)

    print(json.dumps({"FULL": full_metrics, "V2": v2_metrics, "delta": delta, "disagreement": counts}, indent=2), flush=True)
    print(f"wrote {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
