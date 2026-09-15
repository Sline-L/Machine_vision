"""One-shot locked test_scratch evaluation for classifier_only_v1.

Follows docs/capability-extraction/step4-locked-test-protocol.md.
Does NOT tune threshold, fusion, or Q_D rule. Does NOT open CLASSIFY_ONLY.
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

LOCKED_MARKERS_FORBID_IN_VAL = ()  # test_scratch is required here
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
FROZEN_THRESHOLD = 0.5986470981744116
QD_FLOOR = 0.70
U_FLOOR = 0.85


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_test_samples(image_dir: Path, ann_dir: Path):
    text = str(image_dir).replace("\\", "/")
    if "test_scratch" not in text:
        raise SystemExit("locked test requires images under test_scratch")
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
            }
        )
    return samples


def score_mean(runtime: ScratchV5Runtime, image_bgr):
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    scores = []
    with runtime.torch.inference_mode():
        for item, model in runtime.classifiers:
            image = square_rgb_image(rgb, int(item["imgsz"]))
            tensor = runtime.tensor_transform(image).unsqueeze(0).to(runtime.device)
            raw = float(model(tensor).sigmoid()[0, 0].item())
            scores.append(apply_temperature(raw, item.get("temperature", 1.0)))
    return float(scores[0]), float(scores[1]), float(np.mean(scores))


def confusion(labels, probs, threshold):
    tp = fp = tn = fn = 0
    for label, prob in zip(labels, probs):
        pred = prob >= threshold
        if label == 1 and pred:
            tp += 1
        elif label == 0 and pred:
            fp += 1
        elif label == 0 and not pred:
            tn += 1
        else:
            fn += 1
    recall = tp / max(1, tp + fn)
    precision = tp / max(1, tp + fp)
    fpr = fp / max(1, fp + tn)
    specificity = 1.0 - fpr
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "recall": recall,
        "precision": precision,
        "fpr": fpr,
        "specificity": specificity,
        "f1": f1,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-images", type=Path, required=True)
    parser.add_argument("--test-ann", type=Path, required=True)
    parser.add_argument(
        "--model2",
        type=Path,
        default=PROJECT_ROOT / "model" / "model2" / "inference_config.json",
    )
    parser.add_argument(
        "--frozen-config",
        type=Path,
        default=PROJECT_ROOT
        / "docs"
        / "capability-extraction"
        / "configs"
        / "classifier_only_mean.val-frozen.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT
        / "docs"
        / "capability-extraction"
        / "locked-test",
    )
    parser.add_argument("--dataset-commit", default="")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing locked report (forbidden for formal re-run)",
    )
    args = parser.parse_args(argv)

    out = Path(args.out)
    report_path = out / "classifier_only_v1.locked-test.report.json"
    if report_path.is_file() and not args.force:
        raise SystemExit(
            f"Locked report already exists: {report_path}; refuse second formal run "
            "(use --force only intentionally per protocol)"
        )

    frozen = json.loads(Path(args.frozen_config).read_text(encoding="utf-8"))
    threshold = float(frozen["default_threshold"])
    if abs(threshold - FROZEN_THRESHOLD) > 1e-12:
        raise SystemExit(
            f"frozen config threshold {threshold} != protocol {FROZEN_THRESHOLD}"
        )
    if frozen.get("detector") is not None:
        raise SystemExit("frozen config must have detector=null")
    if frozen.get("fusion", {}).get("type") != "classifier_mean":
        raise SystemExit("frozen config fusion must be classifier_mean")

    samples = load_test_samples(args.test_images.resolve(), args.test_ann.resolve())
    if len(samples) != 150:
        raise SystemExit(f"expected 150 test_scratch images, got {len(samples)}")

    runtime = ScratchV5Runtime(args.model2, warmup=True)
    rows = []
    labels = []
    probs = []
    for sample in samples:
        image = cv2.imread(str(sample["path"]))
        if image is None:
            raise SystemExit(f"failed to read {sample['path']}")
        c1, c2, mean_score = score_mean(runtime, image)
        labels.append(sample["label"])
        probs.append(mean_score)
        decision = "REJECT" if mean_score >= threshold else "PASS"
        rows.append(
            {
                "stem": sample["stem"],
                "truth": sample["truth"],
                "label": sample["label"],
                "classifier_1": c1,
                "classifier_2": c2,
                "classifier_mean": mean_score,
                "threshold": threshold,
                "decision": decision,
                "correct": int(
                    (decision == "REJECT" and sample["label"] == 1)
                    or (decision == "PASS" and sample["label"] == 0)
                ),
            }
        )

    metrics = confusion(labels, probs, threshold)
    qd = min(metrics["recall"], metrics["specificity"])
    u_test = 0.5 + 0.5 * qd
    dataset_target_pass = bool(
        metrics["recall"] >= 0.95 and metrics["fpr"] <= 0.20
    )
    mission_contract_pass = bool(qd >= QD_FLOOR)  # binary semantics already PASS in Step 3
    runtime_gate = "OPEN" if mission_contract_pass else "CLOSED"

    n_scratch = sum(labels)
    n_normal = len(labels) - n_scratch

    report = {
        "protocol": "docs/capability-extraction/step4-locked-test-protocol.md",
        "profile_id": "classifier_only_v1",
        "claim": "one_shot_locked_test_scratch",
        "threshold": threshold,
        "fusion": "classifier_mean",
        "detector": "disabled",
        "Q_D_rule": "min(Recall, 1 - FPR)",
        "bbox_acceptance_criterion": False,
        "split": "test_scratch",
        "n_images": len(samples),
        "n_scratch": n_scratch,
        "n_normal": n_normal,
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "tn": metrics["tn"],
        "fn": metrics["fn"],
        "recall": metrics["recall"],
        "fpr": metrics["fpr"],
        "specificity": metrics["specificity"],
        "precision": metrics["precision"],
        "f1": metrics["f1"],
        "Q_D_test": qd,
        "U_test": u_test,
        "dataset_target_pass": dataset_target_pass,
        "mission_contract_pass": mission_contract_pass,
        "runtime_gate": runtime_gate,
        "classify_only_implementation_started": False,
        "rules_changed": False,
        "provenance": {
            "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "frozen_config": str(Path(args.frozen_config).resolve()),
            "frozen_config_sha256": file_sha256(Path(args.frozen_config)),
            "model2": str(Path(args.model2).resolve()),
            "dataset_commit": args.dataset_commit or None,
            "test_images": str(Path(args.test_images).resolve()),
            "test_ann": str(Path(args.test_ann).resolve()),
        },
        "on_fail_discipline": {
            "tune_A": False,
            "rescue_B_on_same_test_scratch_as_locked": False,
        },
    }

    out.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (out / "classifier_only_v1.locked-test.predictions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Locked test — classifier_only_v1",
        "",
        f"- threshold: `{threshold}` (frozen)",
        f"- TP/FP/TN/FN: {metrics['tp']} / {metrics['fp']} / {metrics['tn']} / {metrics['fn']}",
        f"- Recall: {metrics['recall']:.6f}",
        f"- FPR: {metrics['fpr']:.6f}",
        f"- Specificity: {metrics['specificity']:.6f}",
        f"- Precision / F1: {metrics['precision']:.6f} / {metrics['f1']:.6f}",
        f"- Q_D,test: {qd:.6f}",
        f"- U_test: {u_test:.6f}",
        f"- dataset_target_pass: **{dataset_target_pass}**",
        f"- mission_contract_pass: **{mission_contract_pass}**",
        f"- runtime_gate: **{runtime_gate}**",
        "",
        "Rules unchanged. CLASSIFY_ONLY not implemented in this step.",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
