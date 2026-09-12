from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw
from ultralytics import YOLO

from auto_optimize_defects import CLASSES, OUTPUT, WORK, Sample, load_samples, make_split


REPORT = OUTPUT / "final_report.json"
DETAILS = OUTPUT / "final_evaluation.json"
VISUALS = OUTPUT / "final_visuals"


def iou(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    return intersection / max(1e-9, area_left + area_right - intersection)


def evaluate(mode: str, weights: Path, threshold: float, samples: list[Sample], data: Path) -> dict[str, object]:
    model = YOLO(weights)
    tp = fp = fn = 0
    rows = []
    predictions: dict[str, list[tuple[tuple[float, ...], float]]] = {}
    for sample in samples:
        result = model.predict(
            str(sample.image), imgsz=960, conf=threshold, iou=0.7,
            max_det=300, device=0, verbose=False,
        )[0]
        detected = [(tuple(box), float(confidence)) for box, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist())]
        detected.sort(key=lambda item: item[1], reverse=True)
        predictions[sample.stem] = detected
        truth = [tuple(box[1:]) for box in sample.boxes if box[0] == mode]
        unmatched = set(range(len(truth)))
        image_tp = 0
        for box, _ in detected:
            matches = [(iou(box, truth[index]), index) for index in unmatched]
            best_iou, best_index = max(matches, default=(0.0, -1))
            if best_iou >= 0.5:
                image_tp += 1
                unmatched.remove(best_index)
            else:
                fp += 1
        tp += image_tp
        fn += len(unmatched)
        rows.append({"stem": sample.stem, "category": sample.category, "tp": image_tp, "fp": len(detected) - image_tp, "fn": len(unmatched)})
    metrics = model.val(
        data=str(data), split="test", conf=threshold, iou=0.7, imgsz=960,
        batch=16, workers=4, device=0, plots=True, verbose=False,
        project=str(OUTPUT / "metric_runs"), name=mode, exist_ok=True,
    )
    matrix = metrics.confusion_matrix.matrix
    tp, fp, fn = int(matrix[0, 0]), int(matrix[0, 1]), int(matrix[1, 0])
    precision, recall, f1 = float(metrics.box.p[0]), float(metrics.box.r[0]), float(metrics.box.f1[0])
    render(mode, threshold, samples, rows, predictions)
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "threshold": threshold, "per_image": rows}


def render(
    mode: str,
    threshold: float,
    samples: list[Sample],
    rows: list[dict[str, object]],
    predictions: dict[str, list[tuple[tuple[float, ...], float]]],
) -> None:
    output = VISUALS / mode
    output.mkdir(parents=True, exist_ok=True)
    error_stems = [row["stem"] for row in sorted(rows, key=lambda row: (row["fn"] + row["fp"], row["fn"]), reverse=True) if row["fn"] + row["fp"] > 0][:12]
    normal_stems = [row["stem"] for row in rows if row["category"] == "negative"][:4]
    chosen = set(error_stems + normal_stems)
    for sample in samples:
        if sample.stem not in chosen:
            continue
        with Image.open(sample.image) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for name, x1, y1, x2, y2 in sample.boxes:
            if name == mode:
                draw.rectangle((x1, y1, x2, y2), outline=(0, 220, 80), width=3)
        for box, confidence in predictions[sample.stem]:
            draw.rectangle(box, outline=(255, 50, 50), width=3)
            draw.text((box[0], max(0, box[1] - 12)), f"{confidence:.2f}", fill=(255, 50, 50))
        draw.text((8, 8), f"green=GT red=prediction conf>={threshold:.2f}", fill=(255, 220, 0))
        image.save(output / f"{sample.stem}.jpg", quality=95)


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    samples = load_samples()
    assignments = make_split(samples)
    test = [sample for sample in samples if assignments[sample.stem] == "test"]
    output = {}
    for selected in report["selected"]:
        mode = selected["mode"]
        threshold = float(selected["metrics"]["classes"][mode]["conf"])
        data = WORK / "datasets" / f"f_{mode}_light_960_seed42" / "data.yaml"
        output[mode] = evaluate(mode, Path(selected["weights"]), threshold, test, data)
        metrics = selected["metrics"]["classes"][mode]
        metrics.update({key: output[mode][key] for key in ("f1", "tp", "fp", "fn")})
    DETAILS.write_text(json.dumps(output, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    config = {
        "models": {selected["mode"]: {"weights": selected["weights"], "confidence": selected["metrics"]["classes"][selected["mode"]]["conf"], "nms_iou": 0.7, "imgsz": 960} for selected in report["selected"]},
        "strategy": "run both independent models and merge their class-specific detections",
    }
    (OUTPUT / "final_inference_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps({mode: {key: value for key, value in result.items() if key != "per_image"} for mode, result in output.items()}, indent=2))


if __name__ == "__main__":
    main()
