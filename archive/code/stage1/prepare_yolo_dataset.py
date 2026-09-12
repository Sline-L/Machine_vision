from __future__ import annotations

import xml.etree.ElementTree as ET
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASET_ROOT = ROOT / "DATASET"
ANNOTATION_ROOT = DATASET_ROOT / "annotations"
LABEL_ROOT = DATASET_ROOT / "labels"
IMAGE_ROOT = DATASET_ROOT / "images"
CLASS_NAMES = ["gear"]


def voc_box_to_yolo(size: tuple[int, int], box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    width, height = size
    xmin, ymin, xmax, ymax = box
    return (
        ((xmin + xmax) / 2) / width,
        ((ymin + ymax) / 2) / height,
        (xmax - xmin) / width,
        (ymax - ymin) / height,
    )


def xml_to_yolo(xml_path: Path) -> list[str]:
    root = ET.parse(xml_path).getroot()
    width = int(root.findtext("size/width", "0"))
    height = int(root.findtext("size/height", "0"))
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image size in {xml_path}")

    lines: list[str] = []
    for obj in root.findall("object"):
        class_name = obj.findtext("name")
        if class_name not in CLASS_NAMES:
            raise ValueError(f"Unknown class {class_name!r} in {xml_path}")

        box = obj.find("bndbox")
        if box is None:
            continue

        yolo_box = voc_box_to_yolo(
            (width, height),
            (
                float(box.findtext("xmin", "0")),
                float(box.findtext("ymin", "0")),
                float(box.findtext("xmax", "0")),
                float(box.findtext("ymax", "0")),
            ),
        )
        lines.append(f"{CLASS_NAMES.index(class_name)} " + " ".join(f"{value:.6f}" for value in yolo_box))

    return lines


def write_data_yaml() -> None:
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES))
    (DATASET_ROOT / "data.yaml").write_text(
        f"path: {DATASET_ROOT.as_posix()}\n"
        "train: images/train\n"
        "val: images/val_labeled\n"
        "test: images/test\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names:\n{names}\n",
        encoding="utf-8",
    )


def main() -> None:
    generated = 0
    for split_dir in sorted(ANNOTATION_ROOT.glob("*")):
        if not split_dir.is_dir():
            continue
        target_dir = LABEL_ROOT / split_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        for xml_path in sorted(split_dir.glob("*.xml")):
            lines = xml_to_yolo(xml_path)
            (target_dir / f"{xml_path.stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            generated += 1

    val_labeled_dir = IMAGE_ROOT / "val_labeled"
    val_labeled_label_dir = LABEL_ROOT / "val_labeled"
    val_labeled_dir.mkdir(parents=True, exist_ok=True)
    val_labeled_label_dir.mkdir(parents=True, exist_ok=True)
    for xml_path in sorted((ANNOTATION_ROOT / "val").glob("*.xml")):
        source_image = IMAGE_ROOT / "val" / f"{xml_path.stem}.jpg"
        if not source_image.exists():
            raise FileNotFoundError(f"Missing validation image for {xml_path}: {source_image}")
        shutil.copy2(source_image, val_labeled_dir / source_image.name)
        lines = xml_to_yolo(xml_path)
        (val_labeled_label_dir / f"{xml_path.stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_data_yaml()
    print(f"Generated {generated} YOLO label files under {LABEL_ROOT}")
    print(f"Wrote {DATASET_ROOT / 'data.yaml'}")


if __name__ == "__main__":
    main()
