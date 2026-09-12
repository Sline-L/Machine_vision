from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset_defects"
WORK = SOURCE / "scratch_v5"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")


@dataclass(frozen=True)
class Sample:
    stem: str
    split: str
    image: Path
    xml: Path | None
    label: str
    boxes: tuple[tuple[float, float, float, float], ...]
    width: int
    height: int
    dhash: int
    sha256: str
    excluded_from_train: bool = False
    exclusion_reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the scratch-only V5 dataset")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=WORK)
    parser.add_argument("--force", action="store_true", help="Replace only the generated V5 directory")
    return parser.parse_args()


def image_for_stem(directory: Path, stem: str) -> Path | None:
    for extension in IMAGE_EXTENSIONS:
        candidate = directory / f"{stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def image_dhash(path: Path) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = np.asarray(gray, dtype=np.int16)
    bits = (pixels[:, 1:] > pixels[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_xml(path: Path, image_path: Path) -> tuple[int, int, tuple[tuple[float, float, float, float], ...]]:
    root = ET.parse(path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError(f"Missing <size> in {path}")
    width = int(size.findtext("width", "0"))
    height = int(size.findtext("height", "0"))
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid XML image size in {path}: {width}x{height}")
    with Image.open(image_path) as image:
        actual = image.size
    if actual != (width, height):
        raise ValueError(f"Image/XML size mismatch for {path}: image={actual}, xml={(width, height)}")

    boxes = []
    for obj in root.findall("object"):
        name = obj.findtext("name", "").strip()
        if name != "scratch":
            raise ValueError(f"Unexpected class {name!r} in {path}")
        box = obj.find("bndbox")
        if box is None:
            raise ValueError(f"Missing <bndbox> in {path}")
        xmin = float(box.findtext("xmin", "nan"))
        ymin = float(box.findtext("ymin", "nan"))
        xmax = float(box.findtext("xmax", "nan"))
        ymax = float(box.findtext("ymax", "nan"))
        if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
            raise ValueError(f"Invalid box in {path}: {(xmin, ymin, xmax, ymax)}")
        boxes.append((xmin, ymin, xmax, ymax))
    if not boxes:
        raise ValueError(f"Annotated XML contains no scratch boxes: {path}")
    return width, height, tuple(boxes)


def yolo_lines(sample: Sample) -> list[str]:
    lines = []
    for xmin, ymin, xmax, ymax in sample.boxes:
        center_x = (xmin + xmax) / (2 * sample.width)
        center_y = (ymin + ymax) / (2 * sample.height)
        width = (xmax - xmin) / sample.width
        height = (ymax - ymin) / sample.height
        values = (center_x, center_y, width, height)
        if not all(0 <= value <= 1 for value in values):
            raise ValueError(f"Normalized box outside [0,1] for {sample.stem}: {values}")
        lines.append(f"0 {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}")
    return lines


def copy_missing_images(source: Path) -> list[dict[str, str]]:
    copied = []
    for split in ("train", "val"):
        annotation_dir = source / "annotations" / f"{split}_scratch"
        destination_dir = source / "images" / f"{split}_scratch"
        destination_dir.mkdir(parents=True, exist_ok=True)
        for xml_path in sorted(annotation_dir.glob("*.xml")):
            if image_for_stem(destination_dir, xml_path.stem):
                continue
            found = None
            for source_split in (split, "train", "val"):
                found = image_for_stem(source / "images" / source_split, xml_path.stem)
                if found:
                    break
            if found is None:
                raise FileNotFoundError(f"No source image for {xml_path}")
            destination = destination_dir / found.name
            shutil.copy2(found, destination)
            copied.append({"split": split, "stem": xml_path.stem, "source": str(found), "destination": str(destination)})
    return copied


def load_samples(source: Path) -> list[Sample]:
    samples = []
    for split in ("train", "val"):
        image_dir = source / "images" / f"{split}_scratch"
        annotation_dir = source / "annotations" / f"{split}_scratch"
        images = [path for path in sorted(image_dir.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
        if len({path.stem for path in images}) != len(images):
            raise ValueError(f"Duplicate image stems in {image_dir}")
        for image_path in images:
            xml_path = annotation_dir / f"{image_path.stem}.xml"
            if xml_path.is_file():
                width, height, boxes = parse_xml(xml_path, image_path)
                label = "scratch"
                xml_value: Path | None = xml_path
            else:
                with Image.open(image_path) as image:
                    width, height = image.size
                boxes, label, xml_value = (), "normal", None
            samples.append(Sample(
                stem=image_path.stem,
                split=split,
                image=image_path,
                xml=xml_value,
                label=label,
                boxes=boxes,
                width=width,
                height=height,
                dhash=image_dhash(image_path),
                sha256=file_sha256(image_path),
            ))
        image_stems = {path.stem for path in images}
        orphan_xml = sorted(path.name for path in annotation_dir.glob("*.xml") if path.stem not in image_stems)
        if orphan_xml:
            raise FileNotFoundError(f"XML files still missing images in {split}: {orphan_xml}")
    return samples


def mark_train_leaks(samples: list[Sample]) -> tuple[list[Sample], list[dict[str, object]]]:
    train = [sample for sample in samples if sample.split == "train"]
    validation = [sample for sample in samples if sample.split == "val"]
    exclusions: dict[str, set[str]] = {}
    leak_rows = []
    for left in train:
        for right in validation:
            distance = (left.dhash ^ right.dhash).bit_count()
            exact = left.sha256 == right.sha256
            if exact or distance <= 2:
                reason = "exact_sha256" if exact else f"dhash_distance_{distance}"
                exclusions.setdefault(left.stem, set()).add(reason)
                leak_rows.append({
                    "train_stem": left.stem,
                    "val_stem": right.stem,
                    "train_label": left.label,
                    "val_label": right.label,
                    "dhash_distance": distance,
                    "exact_sha256": exact,
                })
    updated = [
        Sample(**{
            **asdict(sample),
            "excluded_from_train": sample.stem in exclusions and sample.split == "train",
            "exclusion_reason": ";".join(sorted(exclusions.get(sample.stem, set()))),
        })
        for sample in samples
    ]
    return updated, leak_rows


def materialize(samples: list[Sample], output: Path) -> None:
    for sample in samples:
        if sample.split == "train" and sample.excluded_from_train:
            continue
        image_dir = output / "images" / sample.split
        label_dir = output / "labels" / sample.split
        class_dir = output / "classification" / sample.split / ("defect" if sample.label == "scratch" else "normal")
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        class_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample.image, image_dir / sample.image.name)
        shutil.copy2(sample.image, class_dir / sample.image.name)
        lines = yolo_lines(sample)
        (label_dir / f"{sample.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")


def write_source_labels(samples: list[Sample], source: Path) -> None:
    for split in ("train", "val"):
        destination = source / "labels" / f"{split}_scratch"
        destination.mkdir(parents=True, exist_ok=True)
        expected = {sample.stem for sample in samples if sample.split == split}
        for stale in destination.glob("*.txt"):
            if stale.stem not in expected:
                stale.unlink()
        for sample in samples:
            if sample.split != split:
                continue
            lines = yolo_lines(sample)
            (destination / f"{sample.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")


def validate(samples: list[Sample], output: Path) -> dict[str, object]:
    raw_counts = {split: dict(Counter(sample.label for sample in samples if sample.split == split)) for split in ("train", "val")}
    usable = [sample for sample in samples if not (sample.split == "train" and sample.excluded_from_train)]
    usable_counts = {split: dict(Counter(sample.label for sample in usable if sample.split == split)) for split in ("train", "val")}
    total_boxes = sum(len(sample.boxes) for sample in samples)
    if len(samples) != 514 or raw_counts != {
        "train": {"scratch": 119, "normal": 245},
        "val": {"scratch": 43, "normal": 107},
    } or total_boxes != 373:
        raise RuntimeError(f"Unexpected redesigned dataset: images={len(samples)}, counts={raw_counts}, boxes={total_boxes}")
    for split in ("train", "val"):
        image_stems = {path.stem for path in (output / "images" / split).iterdir() if path.is_file()}
        label_stems = {path.stem for path in (output / "labels" / split).glob("*.txt")}
        if image_stems != label_stems:
            raise RuntimeError(f"Generated image/label mismatch in {split}")
        for label_path in (output / "labels" / split).glob("*.txt"):
            for line in label_path.read_text(encoding="ascii").splitlines():
                fields = line.split()
                if len(fields) != 5 or fields[0] != "0" or not all(0 <= float(value) <= 1 for value in fields[1:]):
                    raise RuntimeError(f"Invalid YOLO line in {label_path}: {line}")
    return {
        "raw_images": len(samples),
        "raw_counts": raw_counts,
        "usable_images": len(usable),
        "usable_counts": usable_counts,
        "scratch_boxes": total_boxes,
        "excluded_train_near_duplicates": sum(sample.excluded_from_train for sample in samples),
        "class_names": {"0": "scratch"},
        "status": "passed",
    }


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise FileExistsError(f"Generated directory already exists; use --force to rebuild: {output}")
        shutil.rmtree(output)

    copied = copy_missing_images(source)
    samples = load_samples(source)
    samples, leaks = mark_train_leaks(samples)
    write_source_labels(samples, source)
    materialize(samples, output)

    output.mkdir(parents=True, exist_ok=True)
    (output / "data.yaml").write_text(
        f"path: {output.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: scratch\n",
        encoding="ascii",
    )
    with (output / "scratch_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ("stem", "split", "label", "boxes", "image", "xml", "width", "height", "dhash", "sha256", "excluded_from_train", "exclusion_reason")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sample in samples:
            writer.writerow({
                "stem": sample.stem,
                "split": sample.split,
                "label": sample.label,
                "boxes": len(sample.boxes),
                "image": str(sample.image),
                "xml": str(sample.xml or ""),
                "width": sample.width,
                "height": sample.height,
                "dhash": f"{sample.dhash:016x}",
                "sha256": sample.sha256,
                "excluded_from_train": sample.excluded_from_train,
                "exclusion_reason": sample.exclusion_reason,
            })
    with (output / "cross_split_near_duplicates.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ("train_stem", "val_stem", "train_label", "val_label", "dhash_distance", "exact_sha256")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(leaks)
    report = validate(samples, output)
    report["copied_missing_images"] = copied
    report["cross_split_near_duplicate_pairs"] = len(leaks)
    (output / "preflight_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
