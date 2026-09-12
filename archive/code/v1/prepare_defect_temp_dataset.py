from __future__ import annotations

import argparse
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


CLASS_NAMES = ("scratch", "missing_tooth")
CLASS_IDS = {name: index for index, name in enumerate(CLASS_NAMES)}


def parse_annotation(xml_path: Path) -> tuple[tuple[int, int], list[tuple[str, float, float, float, float]]]:
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError(f"Missing <size> in {xml_path}")

    width = int(size.findtext("width", "0"))
    height = int(size.findtext("height", "0"))
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image size in {xml_path}: {width}x{height}")

    objects: list[tuple[str, float, float, float, float]] = []
    for obj in root.findall("object"):
        class_name = obj.findtext("name", "").strip()
        if class_name not in CLASS_IDS:
            raise ValueError(f"Unknown class {class_name!r} in {xml_path}")

        box = obj.find("bndbox")
        if box is None:
            raise ValueError(f"Missing <bndbox> in {xml_path}")
        xmin = float(box.findtext("xmin", "0"))
        ymin = float(box.findtext("ymin", "0"))
        xmax = float(box.findtext("xmax", "0"))
        ymax = float(box.findtext("ymax", "0"))
        if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
            raise ValueError(f"Invalid box in {xml_path}: {(xmin, ymin, xmax, ymax)}")
        objects.append((class_name, xmin, ymin, xmax, ymax))

    return (width, height), objects


def category_for(xml_path: Path) -> str:
    if not xml_path.exists():
        return "negative"
    _, objects = parse_annotation(xml_path)
    names = sorted({obj[0] for obj in objects})
    return "+".join(names) if names else "negative"


def to_yolo_lines(
    size: tuple[int, int], objects: list[tuple[str, float, float, float, float]]
) -> list[str]:
    width, height = size
    lines = []
    for class_name, xmin, ymin, xmax, ymax in objects:
        center_x = ((xmin + xmax) / 2) / width
        center_y = ((ymin + ymax) / 2) / height
        box_width = (xmax - xmin) / width
        box_height = (ymax - ymin) / height
        lines.append(
            f"{CLASS_IDS[class_name]} {center_x:.6f} {center_y:.6f} "
            f"{box_width:.6f} {box_height:.6f}"
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the first 140 defect crops for YOLO training.")
    parser.add_argument("--source", type=Path, default=Path("dataset_defects"))
    parser.add_argument("--output", type=Path, default=Path("dataset_defects/temp_second_model_140"))
    parser.add_argument("--count", type=int, default=140)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    image_dir = source / "images" / "train"
    annotation_dir = source / "annotations" / "train"

    samples: list[tuple[str, Path, Path]] = []
    groups: dict[str, list[tuple[str, Path, Path]]] = defaultdict(list)
    for index in range(1, args.count + 1):
        stem = f"train_{index:03d}"
        image_path = image_dir / f"{stem}.jpg"
        xml_path = annotation_dir / f"{stem}.xml"
        if not image_path.exists():
            raise FileNotFoundError(f"Missing image: {image_path}")
        sample = (stem, image_path, xml_path)
        samples.append(sample)
        groups[category_for(xml_path)].append(sample)

    rng = random.Random(args.seed)
    split_by_stem: dict[str, str] = {}
    for group_samples in groups.values():
        rng.shuffle(group_samples)
        val_count = round(len(group_samples) * args.val_ratio)
        val_stems = {sample[0] for sample in group_samples[:val_count]}
        for stem, _, _ in group_samples:
            split_by_stem[stem] = "val" if stem in val_stems else "train"

    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)
        (output / "annotations" / split).mkdir(parents=True, exist_ok=True)

    stats: Counter[str] = Counter()
    object_stats: Counter[str] = Counter()
    manifest_lines = ["stem,split,category,objects"]
    for stem, image_path, xml_path in samples:
        split = split_by_stem[stem]
        category = category_for(xml_path)
        shutil.copy2(image_path, output / "images" / split / image_path.name)

        objects: list[tuple[str, float, float, float, float]] = []
        size = (0, 0)
        if xml_path.exists():
            shutil.copy2(xml_path, output / "annotations" / split / xml_path.name)
            size, objects = parse_annotation(xml_path)

        label_path = output / "labels" / split / f"{stem}.txt"
        label_path.write_text("\n".join(to_yolo_lines(size, objects)) + ("\n" if objects else ""), encoding="ascii")

        stats[f"{split}/{category}"] += 1
        for obj in objects:
            object_stats[f"{split}/{obj[0]}"] += 1
        manifest_lines.append(f"{stem},{split},{category},{len(objects)}")

    yaml_path = output / "data.yaml"
    yaml_path.write_text(
        "path: " + output.as_posix() + "\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: scratch\n"
        "  1: missing_tooth\n",
        encoding="ascii",
    )
    (output / "split_manifest.csv").write_text("\n".join(manifest_lines) + "\n", encoding="ascii")

    print(f"Prepared {len(samples)} images in {output}")
    for key in sorted(stats):
        print(f"  {key}: {stats[key]} images")
    for key in sorted(object_stats):
        print(f"  {key}: {object_stats[key]} boxes")


if __name__ == "__main__":
    main()
