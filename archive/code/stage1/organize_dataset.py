from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW_IMAGE_ROOT = ROOT / "image"
DATASET_ROOT = ROOT / "DATASET"
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


def update_xml_metadata(xml_path: Path, image_name: str) -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    filename = root.find("filename")
    if filename is not None:
        filename.text = image_name
    path = root.find("path")
    if path is not None:
        path.text = str((DATASET_ROOT / "images" / "train" / image_name).resolve())
    tree.write(xml_path, encoding="utf-8", xml_declaration=False)


def rename_train() -> int:
    image_dir = DATASET_ROOT / "images" / "train"
    xml_dir = DATASET_ROOT / "labels" / "train"
    annotation_dir = DATASET_ROOT / "annotations" / "train"
    label_dir = DATASET_ROOT / "labels" / "train"
    temp_dir = DATASET_ROOT / "_rename_tmp" / "train"

    temp_dir.mkdir(parents=True, exist_ok=True)
    annotation_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(image_dir.glob("*.jpg"))
    for index, image_path in enumerate(images, 1):
        original_stem = image_path.stem
        new_stem = f"train_{index:03d}"
        temp_image = temp_dir / f"{new_stem}.jpg"
        image_path.rename(temp_image)

        old_xml = xml_dir / f"{original_stem}.xml"
        if old_xml.exists():
            new_xml = annotation_dir / f"{new_stem}.xml"
            old_xml.rename(new_xml)
            update_xml_metadata(new_xml, f"{new_stem}.jpg")
            yolo_lines = xml_to_yolo(new_xml)
            (label_dir / f"{new_stem}.txt").write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")

    for temp_image in sorted(temp_dir.glob("*.jpg")):
        temp_image.rename(image_dir / temp_image.name)

    return len(images)


def move_and_rename_image_split(split: str) -> int:
    source_dir = RAW_IMAGE_ROOT / split
    target_dir = DATASET_ROOT / "images" / split
    target_dir.mkdir(parents=True, exist_ok=True)

    source_images = sorted(source_dir.glob("*.jpg"))
    for index, image_path in enumerate(source_images, 1):
        target = target_dir / f"{split}_{index:03d}.jpg"
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite {target}")
        shutil.move(str(image_path), str(target))

    return len(source_images)


def write_data_yaml() -> None:
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES))
    (DATASET_ROOT / "data.yaml").write_text(
        f"path: {DATASET_ROOT.as_posix()}\n"
        "train: images/train\n"
        "val: images/train\n"
        "test: images/test\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names:\n{names}\n",
        encoding="utf-8",
    )


def main() -> None:
    train_count = rename_train()
    val_count = move_and_rename_image_split("val")
    test_count = move_and_rename_image_split("test")
    write_data_yaml()
    print(f"train renamed: {train_count}")
    print(f"val moved/renamed: {val_count}")
    print(f"test moved/renamed: {test_count}")
    print(f"dataset: {DATASET_ROOT}")


if __name__ == "__main__":
    main()
