from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "dataset_defects" / "images"
DEFAULT_WEIGHTS = ROOT / "runs" / "gear_yolo26n_496train_50val_fixed" / "weights" / "best.pt"
DEFAULT_OUTPUT = ROOT / "dataset_defects" / "gear_detection"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))

from ultralytics import YOLO  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect gears in dataset_defects and crop gear ROIs.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Image root to scan recursively.")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="Gear detector weights.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output root for crops and previews.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.7, help="NMS IoU threshold.")
    parser.add_argument("--pad", type=float, default=0.20, help="Padding ratio around detected gear box.")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--device", default=None, help="Inference device, for example 0 or cpu. Omit for auto.")
    parser.add_argument("--all-boxes", action="store_true", help="Crop every detected box instead of only the best box.")
    return parser.parse_args()


def list_images(source: Path) -> list[Path]:
    return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def clean_output(output: Path) -> None:
    for child in ("crops", "predictions"):
        directory = output / child
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file():
                    path.unlink()
        directory.mkdir(parents=True, exist_ok=True)


def expand_box(xyxy: list[float], image_width: int, image_height: int, pad: float) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    dx = box_width * pad
    dy = box_height * pad
    return (
        max(0, int(round(x1 - dx))),
        max(0, int(round(y1 - dy))),
        min(image_width, int(round(x2 + dx))),
        min(image_height, int(round(y2 + dy))),
    )


def unique_crop_name(image_path: Path, box_index: int, confidence: float, all_boxes: bool) -> str:
    suffix = image_path.suffix.lower()
    if all_boxes:
        return f"{image_path.stem}_box{box_index:03d}_conf{confidence:.3f}{suffix}"
    return f"{image_path.stem}{suffix}"


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    weights = args.weights.resolve()
    output = args.output.resolve()

    if not source.exists():
        raise FileNotFoundError(f"Missing source directory: {source}")
    if not weights.exists():
        raise FileNotFoundError(f"Missing weights: {weights}")

    images = list_images(source)
    clean_output(output)

    model = YOLO(str(weights))
    rows: list[dict[str, object]] = []
    no_detection: list[str] = []

    for index, image_path in enumerate(images, start=1):
        rel_parent = image_path.parent.relative_to(source)
        prediction_dir = output / "predictions" / rel_parent
        crop_dir = output / "crops" / rel_parent
        prediction_dir.mkdir(parents=True, exist_ok=True)
        crop_dir.mkdir(parents=True, exist_ok=True)

        predict_kwargs = {
            "source": str(image_path),
            "conf": args.conf,
            "iou": args.iou,
            "imgsz": args.imgsz,
            "save": False,
            "verbose": False,
        }
        if args.device is not None:
            predict_kwargs["device"] = args.device
        result = model.predict(**predict_kwargs)[0]

        plotted_bgr = result.plot()
        Image.fromarray(plotted_bgr[..., ::-1]).save(prediction_dir / image_path.name)

        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            no_detection.append(str(image_path.relative_to(source)))
            continue

        xyxys = boxes.xyxy.cpu().tolist()
        confs = boxes.conf.cpu().tolist()
        class_ids = [int(value) for value in boxes.cls.cpu().tolist()]
        detections = sorted(
            zip(xyxys, confs, class_ids, range(1, len(xyxys) + 1)),
            key=lambda item: item[1],
            reverse=True,
        )
        if not args.all_boxes:
            detections = detections[:1]

        with Image.open(image_path) as image:
            image_width, image_height = image.size
            for xyxy, confidence, class_id, box_index in detections:
                crop_box = expand_box(xyxy, image_width, image_height, args.pad)
                crop_name = unique_crop_name(image_path, box_index, float(confidence), args.all_boxes)
                crop_path = crop_dir / crop_name
                image.crop(crop_box).save(crop_path)
                rows.append(
                    {
                        "source_image": str(image_path.relative_to(source)),
                        "crop_path": str(crop_path.relative_to(output)),
                        "box_index": box_index,
                        "class_id": class_id,
                        "confidence": f"{float(confidence):.6f}",
                        "x1": f"{float(xyxy[0]):.2f}",
                        "y1": f"{float(xyxy[1]):.2f}",
                        "x2": f"{float(xyxy[2]):.2f}",
                        "y2": f"{float(xyxy[3]):.2f}",
                        "pad_x1": crop_box[0],
                        "pad_y1": crop_box[1],
                        "pad_x2": crop_box[2],
                        "pad_y2": crop_box[3],
                        "image_width": image_width,
                        "image_height": image_height,
                    }
                )

        if index % 50 == 0:
            print(f"Processed {index}/{len(images)} images")

    csv_path = output / "gear_detections.csv"
    fieldnames = [
        "source_image",
        "crop_path",
        "box_index",
        "class_id",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
        "pad_x1",
        "pad_y1",
        "pad_x2",
        "pad_y2",
        "image_width",
        "image_height",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    no_detection_path = output / "no_detection.txt"
    no_detection_path.write_text("\n".join(no_detection) + ("\n" if no_detection else ""), encoding="utf-8")

    print(f"Images: {len(images)}")
    print(f"Crops: {len(rows)}")
    print(f"No detections: {len(no_detection)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
