from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from statistics import mean

from PIL import Image


ROOT = Path(__file__).resolve().parent
DATASET_ROOT = ROOT / "DATASET"
DEFAULT_WEIGHTS = ROOT / "runs" / "gear_yolo26n_496train_50val_fixed" / "weights" / "best.pt"
OUTPUT_ROOT = ROOT / "outputs"
CLASS_NAMES = ["gear"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))

from ultralytics import YOLO  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run post-training YOLO evaluation, val pseudo-labeling, and padded test crops."
    )
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="Path to trained YOLO weights.")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold for pseudo labels and crops.")
    parser.add_argument("--iou", type=float, default=0.7, help="NMS IoU threshold.")
    parser.add_argument("--pad", type=float, default=0.15, help="Crop padding ratio relative to each detected box.")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--device", default="0", help="Inference device, for example 0 for GPU or cpu.")
    parser.add_argument("--limit-test", type=int, default=0, help="Optional dry-run limit for test images.")
    parser.add_argument("--limit-val", type=int, default=0, help="Optional dry-run limit for unlabeled val images.")
    parser.add_argument(
        "--overwrite-auto-labels",
        action="store_true",
        help="Overwrite existing auto-generated labels, but never overwrite the first 50 labeled val files.",
    )
    return parser.parse_args()


def list_images(directory: Path) -> list[Path]:
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def ensure_weights(weights: Path) -> Path:
    weights = weights.resolve()
    if not weights.exists():
        raise FileNotFoundError(
            f"Missing weights: {weights}. Wait for training to write best.pt, or pass --weights explicitly."
        )
    return weights


def clean_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()


def expand_box(
    xyxy: tuple[float, float, float, float], image_width: int, image_height: int, pad: float
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    dx = box_width * pad
    dy = box_height * pad
    left = max(0, int(round(x1 - dx)))
    top = max(0, int(round(y1 - dy)))
    right = min(image_width, int(round(x2 + dx)))
    bottom = min(image_height, int(round(y2 + dy)))
    return left, top, right, bottom


def yolo_line(
    class_id: int, xyxy: tuple[float, float, float, float], image_width: int, image_height: int
) -> str:
    x1, y1, x2, y2 = xyxy
    x_center = ((x1 + x2) / 2) / image_width
    y_center = ((y1 + y2) / 2) / image_height
    width = (x2 - x1) / image_width
    height = (y2 - y1) / image_height
    return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"


def prediction_rows(result, image_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return rows

    xyxys = boxes.xyxy.cpu().tolist()
    confs = boxes.conf.cpu().tolist()
    class_ids = [int(value) for value in boxes.cls.cpu().tolist()]
    for index, (xyxy, conf, class_id) in enumerate(zip(xyxys, confs, class_ids), start=1):
        rows.append(
            {
                "image": image_path.name,
                "box_index": index,
                "class_id": class_id,
                "class_name": CLASS_NAMES[class_id] if class_id < len(CLASS_NAMES) else str(class_id),
                "confidence": float(conf),
                "x1": float(xyxy[0]),
                "y1": float(xyxy[1]),
                "x2": float(xyxy[2]),
                "y2": float(xyxy[3]),
            }
        )
    return rows


def save_plot(result, output_path: Path) -> None:
    plotted_bgr = result.plot()
    plotted_rgb = plotted_bgr[..., ::-1]
    Image.fromarray(plotted_rgb).save(output_path)


def run_test_predictions(model: YOLO, args: argparse.Namespace) -> dict[str, object]:
    test_images = list_images(DATASET_ROOT / "images" / "test")
    if args.limit_test > 0:
        test_images = test_images[: args.limit_test]

    predictions_dir = OUTPUT_ROOT / "test_predictions"
    crops_dir = OUTPUT_ROOT / "test_crops"
    clean_directory(predictions_dir)
    clean_directory(crops_dir)

    rows: list[dict[str, object]] = []
    no_detection_images: list[str] = []
    total_boxes = 0

    for image_path in test_images:
        result = model.predict(
            source=str(image_path),
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            save=False,
            verbose=False,
        )[0]
        save_plot(result, predictions_dir / image_path.name)

        image_rows = prediction_rows(result, image_path)
        if not image_rows:
            no_detection_images.append(image_path.name)
            continue

        with Image.open(image_path) as image:
            image_width, image_height = image.size
            for row in image_rows:
                xyxy = (row["x1"], row["y1"], row["x2"], row["y2"])
                padded = expand_box(xyxy, image_width, image_height, args.pad)
                crop_name = (
                    f"{image_path.stem}_box{int(row['box_index']):03d}_"
                    f"conf{float(row['confidence']):.3f}{image_path.suffix.lower()}"
                )
                crop_path = crops_dir / crop_name
                image.crop(padded).save(crop_path)
                row.update(
                    {
                        "pad_x1": padded[0],
                        "pad_y1": padded[1],
                        "pad_x2": padded[2],
                        "pad_y2": padded[3],
                        "crop_path": str(crop_path),
                    }
                )
                rows.append(row)
                total_boxes += 1

    csv_path = OUTPUT_ROOT / "test_predictions.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image",
        "box_index",
        "class_id",
        "class_name",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
        "pad_x1",
        "pad_y1",
        "pad_x2",
        "pad_y2",
        "crop_path",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    confidences = [float(row["confidence"]) for row in rows]
    return {
        "test_images": len(test_images),
        "test_detections": total_boxes,
        "test_images_without_detections": no_detection_images,
        "mean_confidence": mean(confidences) if confidences else 0.0,
        "predictions_dir": str(predictions_dir),
        "crops_dir": str(crops_dir),
        "csv": str(csv_path),
    }


def pseudo_label_val(model: YOLO, args: argparse.Namespace) -> dict[str, object]:
    val_images = list_images(DATASET_ROOT / "images" / "val")
    val_label_dir = DATASET_ROOT / "labels" / "val"
    val_label_dir.mkdir(parents=True, exist_ok=True)

    pending = [path for path in val_images if not (val_label_dir / f"{path.stem}.txt").exists()]
    if args.limit_val > 0:
        pending = pending[: args.limit_val]

    written = 0
    no_detection_images: list[str] = []

    for image_path in pending:
        label_path = val_label_dir / f"{image_path.stem}.txt"
        if label_path.exists() and not args.overwrite_auto_labels:
            continue

        result = model.predict(
            source=str(image_path),
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            save=False,
            verbose=False,
        )[0]

        with Image.open(image_path) as image:
            image_width, image_height = image.size

        rows = prediction_rows(result, image_path)
        lines = [
            yolo_line(
                int(row["class_id"]),
                (float(row["x1"]), float(row["y1"]), float(row["x2"]), float(row["y2"])),
                image_width,
                image_height,
            )
            for row in rows
        ]
        if not lines:
            no_detection_images.append(image_path.name)

        label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        written += 1

    return {
        "val_images": len(val_images),
        "val_labels_written": written,
        "val_images_without_detections": no_detection_images,
        "val_labels_total": len(list(val_label_dir.glob("*.txt"))),
    }


def maybe_run_test_metrics(model: YOLO, args: argparse.Namespace) -> dict[str, object]:
    test_label_dir = DATASET_ROOT / "labels" / "test"
    test_label_count = len(list(test_label_dir.glob("*.txt"))) if test_label_dir.exists() else 0
    test_image_count = len(list_images(DATASET_ROOT / "images" / "test"))
    if test_label_count == 0:
        return {
            "available": False,
            "reason": "DATASET/labels/test is empty, so real mAP/accuracy cannot be computed.",
            "test_label_count": 0,
        }

    metrics = model.val(
        data=str(DATASET_ROOT / "data.yaml"),
        split="test",
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
        project=str(ROOT / "runs"),
        name="gear_yolo26n_test_eval",
        exist_ok=True,
        verbose=False,
    )
    return {
        "available": True,
        "test_label_count": test_label_count,
        "test_image_count": test_image_count,
        "mAP50": float(metrics.box.map50),
        "mAP50_95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
    }


def write_full_val_yaml() -> Path:
    yaml_path = DATASET_ROOT / "data_full_val.yaml"
    yaml_path.write_text(
        f"path: {DATASET_ROOT.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        f"nc: {len(CLASS_NAMES)}\n"
        "names:\n"
        + "".join(f"  {index}: {name}\n" for index, name in enumerate(CLASS_NAMES)),
        encoding="utf-8",
    )
    return yaml_path


def write_summary(summary: dict[str, object]) -> Path:
    path = OUTPUT_ROOT / "post_training_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    weights = ensure_weights(args.weights)
    model = YOLO(str(weights))

    test_summary = run_test_predictions(model, args)
    val_summary = pseudo_label_val(model, args)
    metrics_summary = maybe_run_test_metrics(model, args)
    full_val_yaml = write_full_val_yaml()

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "weights": str(weights),
        "conf": args.conf,
        "iou": args.iou,
        "pad": args.pad,
        "imgsz": args.imgsz,
        "device": args.device,
        "test": test_summary,
        "val_pseudo_labels": val_summary,
        "test_metrics": metrics_summary,
        "full_val_yaml": str(full_val_yaml),
    }
    summary_path = write_summary(summary)

    print(f"Post-training summary: {summary_path}")
    print(f"Test detections: {test_summary['test_detections']} from {test_summary['test_images']} images")
    print(f"Mean confidence: {test_summary['mean_confidence']:.4f}")
    print(f"Val labels total: {val_summary['val_labels_total']}")
    if not metrics_summary["available"]:
        print(metrics_summary["reason"])


if __name__ == "__main__":
    main()
