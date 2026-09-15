from __future__ import annotations

import csv
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from train_missing_hole_v1 import (
    ClassifierExperiment,
    DetectorExperiment,
    Sample,
    evaluate_probabilities,
    predict_classifier,
    predict_detector,
    rank_key,
    train_classifier,
    train_detector,
    workers,
)


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset_defects"
WORK = SOURCE / "missing_hole_v1"
OUTPUT = ROOT / "outputs" / "unified_defect_v1"
DOCS = ROOT / "docs" / "missing_hole_v1"
SEED = 20260913


def save_progress(rows: list[dict[str, object]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "leaderboard.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    experiment_dir = DOCS / "experiments"
    experiment_dir.mkdir(parents=True, exist_ok=True)
    row = rows[-1]
    point = row["primary"]
    lines = [
        f"# {row['name']}", "", "- 任务：scratch + missing_hole 统一模型",
        f"- 类型：`{row['kind']}`", f"- 输入：`{row['imgsz']}`", f"- 权重：`{row['weights']}`", "",
        "| Recall | Precision | F1 | FPR | TP/FP/TN/FN |", "|---:|---:|---:|---:|---:|",
        f"| {point['recall']:.4f} | {point['precision']:.4f} | {point['f1']:.4f} | {point['fpr']:.4f} | {point['tp']}/{point['fp']}/{point['tn']}/{point['fn']} |",
        "", "该结果只使用联合验证集，独立 test 未读取。", "",
    ]
    (experiment_dir / f"{row['name']}.md").write_text("\n".join(lines), encoding="utf-8")


def master_rows() -> dict[str, dict[str, str]]:
    with (WORK / "master_manifest.csv").open(encoding="utf-8-sig") as handle:
        return {row["stem"]: row for row in csv.DictReader(handle) if row["source_split"] == "train"}


def build_samples() -> list[Sample]:
    master = master_rows()
    curated = {path.stem: path for path in (SOURCE / "images" / "train_scratch").glob("*") if path.is_file()}
    samples = []
    for stem, row in master.items():
        scratch_known = stem in curated
        missing = bool(int(row["defect"]))
        if not scratch_known and not missing:
            continue
        scratch = (SOURCE / "annotations" / "train_scratch" / f"{stem}.xml").is_file() if scratch_known else False
        image = curated.get(stem, Path(row["image"]))
        with Image.open(image) as opened:
            width, height = opened.size
        classes = tuple(name for name, present in (("scratch", scratch), ("missing_hole", missing)) if present)
        samples.append(Sample(stem, row["split"], int(scratch or missing), image, classes, bool(int(row["has_difficult"])), bool(int(row["all_difficult"])), width, height))
    if len(samples) != 437 or sum(sample.label for sample in samples) != 285:
        raise RuntimeError(f"Unexpected reliable joint dataset: images={len(samples)} positive={sum(sample.label for sample in samples)}")
    return samples


def boxes(path: Path) -> list[tuple[float, float, float, float]]:
    if not path.is_file():
        return []
    root = ET.parse(path).getroot()
    result = []
    for obj in root.findall("object"):
        node = obj.find("bndbox")
        if node is not None:
            result.append(tuple(float(node.findtext(key, "0")) for key in ("xmin", "ymin", "xmax", "ymax")))
    return result


def link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def materialize_detectors(samples: list[Sample]) -> None:
    master = master_rows()
    curated = {path.stem: path for path in (SOURCE / "images" / "train_scratch").glob("*") if path.is_file()}
    common = [sample for sample in samples if sample.stem in curated]
    if len(common) != 364:
        raise RuntimeError(f"Expected 364 fully supervised images, got {len(common)}")
    for scheme, names in (("joint_one_class", ["any_defect"]), ("joint_two_class", ["scratch", "missing_hole"])):
        root = WORK / "yolo" / f"{scheme}_include_difficult"
        for sample in common:
            split = master[sample.stem]["split"]
            link(sample.image, root / "images" / split / sample.image.name)
            scratch_boxes = boxes(SOURCE / "annotations" / "train_scratch" / f"{sample.stem}.xml")
            missing_boxes = boxes(SOURCE / "annotations" / "train_missing_tooth" / f"{sample.stem}.xml")
            lines = []
            for class_id, source_boxes in ((0, scratch_boxes), ((0 if scheme == "joint_one_class" else 1), missing_boxes)):
                for xmin, ymin, xmax, ymax in source_boxes:
                    cx, cy = (xmin + xmax) / (2 * sample.width), (ymin + ymax) / (2 * sample.height)
                    width, height = (xmax - xmin) / sample.width, (ymax - ymin) / sample.height
                    lines.append(f"{class_id} {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}")
            label = root / "labels" / split / f"{sample.stem}.txt"
            label.parent.mkdir(parents=True, exist_ok=True)
            label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")
        yaml = [f"path: {root.as_posix()}", "train: images/train", "val: images/val", "names:"] + [f"  {index}: {name}" for index, name in enumerate(names)]
        (root / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="ascii")


def main() -> None:
    samples = build_samples()
    materialize_detectors(samples)
    worker_count = workers(0)
    val = [sample for sample in samples if sample.split == "val"]
    rows = []
    classifier_artifacts = []
    for family in ("resnet18", "efficientnet_b0", "yolo_cls"):
        experiment = ClassifierExperiment(f"joint_cls_{family}_512", family, 512, "include_difficult", 80, "joint", SEED)
        weights = train_classifier(experiment, samples, worker_count)
        best = None
        for tta in ("none", "flip", "rot90"):
            probabilities = predict_classifier(weights, experiment, val, tta)
            evaluation = evaluate_probabilities(val, probabilities)
            evaluation["tta"] = tta
            if best is None or rank_key(evaluation) > rank_key(best[0]):
                best = (evaluation, probabilities)
        evaluation, probabilities = best
        calibrated = evaluation.pop("probabilities")
        row = {"name": experiment.name, "kind": "classifier", "family": family, "imgsz": 512, "weights": str(weights), **evaluation}
        rows.append(row)
        save_progress(rows)
        classifier_artifacts.append((row, calibrated))
    detector_rows = []
    common = [sample for sample in samples if (SOURCE / "images" / "train_scratch" / sample.image.name).is_file()]
    common_val = [sample for sample in common if sample.split == "val"]
    for scheme in ("joint_one_class", "joint_two_class"):
        experiment = DetectorExperiment(f"joint_det_{scheme}_p2_960", scheme, "include_difficult", "p2", 960, 80, "joint", SEED)
        weights = train_detector(experiment, worker_count)
        probabilities = predict_detector(weights, common_val, 960)
        evaluation = evaluate_probabilities(common_val, probabilities)
        evaluation.pop("probabilities")
        detector_rows.append({"name": experiment.name, "kind": "detector", "scheme": scheme, "imgsz": 960, "weights": str(weights), **evaluation})
        save_progress(rows + detector_rows)
    winner, _ = max(classifier_artifacts, key=lambda item: rank_key(item[0]))
    final = OUTPUT / "final"
    final.mkdir(parents=True, exist_ok=True)
    destination = final / "unified_classifier.pt"
    shutil.copy2(winner["weights"], destination)
    config = {"version": "unified_defect_v1", "models": [{"name": winner["name"], "kind": "classifier", "family": winner["family"], "weights": str(destination), "imgsz": winner["imgsz"], "tta": winner["tta"], "temperature": winner["temperature"]}], "fusion": {"type": "classifier", "models": [winner["name"]]}, "default_threshold": winner["primary"]["threshold"], "operating_points": winner["operating_points"], "test_used": False}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "inference_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "leaderboard.json").write_text(json.dumps(rows + detector_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Scratch + Missing Hole 单模型实验", "", "可靠联合训练集为 437 张：364 张双任务监督完整图片，加 73 张额外明确 missing_hole 正样本；59 张 scratch 状态未知的负候选已排除。", "", "| 模型 | 类型 | Recall | Precision | FPR |", "|---|---|---:|---:|---:|"]
    for row in rows + detector_rows:
        point = row["primary"]
        lines.append(f"| {row['name']} | {row['kind']} | {point['recall']:.4f} | {point['precision']:.4f} | {point['fpr']:.4f} |")
    lines += ["", f"精简版选择：`{winner['name']}`。独立 test 尚未读取。", ""]
    (DOCS / "统一模型实验.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"winner": winner["name"], "primary": winner["primary"], "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
