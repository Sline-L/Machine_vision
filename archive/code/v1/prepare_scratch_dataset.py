from __future__ import annotations

import argparse
import csv
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


TARGET_CLASS = "scratch"
EXCLUDED_CLASS = "missing_tooth"


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
        box = obj.find("bndbox")
        if not class_name or box is None:
            raise ValueError(f"Invalid object in {xml_path}")

        xmin = float(box.findtext("xmin", "0"))
        ymin = float(box.findtext("ymin", "0"))
        xmax = float(box.findtext("xmax", "0"))
        ymax = float(box.findtext("ymax", "0"))
        if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
            raise ValueError(f"Invalid box in {xml_path}: {(xmin, ymin, xmax, ymax)}")
        objects.append((class_name, xmin, ymin, xmax, ymax))

    return (width, height), objects


def yolo_lines(
    size: tuple[int, int], objects: list[tuple[str, float, float, float, float]]
) -> list[str]:
    width, height = size
    lines: list[str] = []
    for _, xmin, ymin, xmax, ymax in objects:
        center_x = ((xmin + xmax) / 2) / width
        center_y = ((ymin + ymax) / 2) / height
        box_width = (xmax - xmin) / width
        box_height = (ymax - ymin) / height
        values = (center_x, center_y, box_width, box_height)
        if not all(0 <= value <= 1 for value in values):
            raise ValueError(f"Normalized box is outside [0, 1]: {values}")
        lines.append(f"0 {center_x:.6f} {center_y:.6f} {box_width:.6f} {box_height:.6f}")
    return lines


def validate_output(output: Path, expected_boxes: int) -> None:
    image_stems: dict[str, set[str]] = {}
    label_stems: dict[str, set[str]] = {}
    total_boxes = 0
    positive_counts: Counter[str] = Counter()

    for split in ("train", "val"):
        image_stems[split] = {path.stem for path in (output / "images" / split).glob("*.jpg")}
        label_stems[split] = {path.stem for path in (output / "labels" / split).glob("*.txt")}
        if image_stems[split] != label_stems[split]:
            raise ValueError(f"Image/label mismatch in {split}")

        for label_path in (output / "labels" / split).glob("*.txt"):
            lines = [line.strip() for line in label_path.read_text(encoding="ascii").splitlines() if line.strip()]
            if lines:
                positive_counts[split] += 1
            for line in lines:
                fields = line.split()
                if len(fields) != 5 or fields[0] != "0":
                    raise ValueError(f"Invalid scratch label in {label_path}: {line}")
                values = [float(value) for value in fields[1:]]
                if not all(0 <= value <= 1 for value in values):
                    raise ValueError(f"Label outside [0, 1] in {label_path}: {line}")
                total_boxes += 1

    if len(image_stems["train"]) != 169 or len(image_stems["val"]) != 42:
        raise ValueError("Unexpected split size")
    if positive_counts != Counter({"train": 63, "val": 16}):
        raise ValueError(f"Unexpected positive split: {dict(positive_counts)}")
    if total_boxes != expected_boxes:
        raise ValueError(f"Expected {expected_boxes} boxes, found {total_boxes}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a scratch-only YOLO dataset from the first 343 images.")
    parser.add_argument("--source", type=Path, default=Path("dataset_defects"))
    parser.add_argument("--output", type=Path, default=Path("dataset_defects/temp_scratch_model_211_from_343"))
    parser.add_argument("--count", type=int, default=343)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")

    image_dir = source / "images" / "train"
    annotation_dir = source / "annotations" / "train"
    included: dict[str, list[tuple[str, Path, Path | None, tuple[int, int] | None, list[tuple[str, float, float, float, float]]]]] = defaultdict(list)
    excluded: list[tuple[str, str]] = []

    for index in range(1, args.count + 1):
        stem = f"train_{index:03d}"
        image_path = image_dir / f"{stem}.jpg"
        xml_path = annotation_dir / f"{stem}.xml"
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        if not xml_path.exists():
            included["negative"].append((stem, image_path, None, None, []))
            continue

        size, objects = parse_annotation(xml_path)
        classes = {obj[0] for obj in objects}
        unknown = classes - {TARGET_CLASS, EXCLUDED_CLASS}
        if unknown:
            raise ValueError(f"Unknown classes in {xml_path}: {sorted(unknown)}")
        if classes == {TARGET_CLASS}:
            included[TARGET_CLASS].append((stem, image_path, xml_path, size, objects))
        elif classes == {EXCLUDED_CLASS}:
            excluded.append((stem, EXCLUDED_CLASS))
        else:
            raise ValueError(f"Mixed or empty annotation is not allowed in {xml_path}: {sorted(classes)}")

    if len(included[TARGET_CLASS]) != 79 or len(included["negative"]) != 132 or len(excluded) != 132:
        raise ValueError(
            "Source counts changed: "
            f"scratch={len(included[TARGET_CLASS])}, negative={len(included['negative'])}, "
            f"excluded={len(excluded)}"
        )

    rng = random.Random(args.seed)
    split_by_stem: dict[str, str] = {}
    val_counts = {TARGET_CLASS: 16, "negative": 26}
    for category in (TARGET_CLASS, "negative"):
        samples = included[category][:]
        rng.shuffle(samples)
        val_stems = {sample[0] for sample in samples[: val_counts[category]]}
        for stem, *_ in samples:
            split_by_stem[stem] = "val" if stem in val_stems else "train"

    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
        (output / "annotations" / split).mkdir(parents=True)

    manifest_rows: list[dict[str, str | int]] = []
    total_boxes = 0
    for category in (TARGET_CLASS, "negative"):
        for stem, image_path, xml_path, size, objects in included[category]:
            split = split_by_stem[stem]
            shutil.copy2(image_path, output / "images" / split / image_path.name)
            if xml_path is not None:
                shutil.copy2(xml_path, output / "annotations" / split / xml_path.name)
                lines = yolo_lines(size, objects)  # type: ignore[arg-type]
            else:
                lines = []
            (output / "labels" / split / f"{stem}.txt").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="ascii"
            )
            total_boxes += len(lines)
            manifest_rows.append(
                {"stem": stem, "split": split, "source_category": category, "action": "included", "boxes": len(lines)}
            )

    for stem, category in excluded:
        manifest_rows.append(
            {"stem": stem, "split": "", "source_category": category, "action": "excluded", "boxes": 0}
        )

    with (output / "split_manifest.csv").open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=("stem", "split", "source_category", "action", "boxes"))
        writer.writeheader()
        writer.writerows(sorted(manifest_rows, key=lambda row: str(row["stem"])))

    (output / "data.yaml").write_text(
        f"path: {output.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: scratch\n",
        encoding="ascii",
    )

    validate_output(output, expected_boxes=159)
    print(f"Prepared scratch-only dataset: {output}")
    print("  train: 169 images (63 scratch, 106 negative)")
    print("  val: 42 images (16 scratch, 26 negative)")
    print(f"  scratch boxes: {total_boxes}")
    print(f"  excluded missing_tooth images: {len(excluded)}")
    print("Preflight data validation passed")


if __name__ == "__main__":
    main()
