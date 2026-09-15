from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset_defects"
OUTPUT = SOURCE / "missing_hole_v1"
SEED = 20260913
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
CLASS_SCHEMES = {
    "three_class": ({"bottom": 0, "oblique": 1, "side": 2}, ["bottom", "oblique", "side"]),
    "two_class": ({"bottom": 0, "oblique": 0, "side": 1}, ["bottom_oblique", "side"]),
    "one_class": ({"bottom": 0, "oblique": 0, "side": 0}, ["missing_hole"]),
}


@dataclass(frozen=True)
class Box:
    name: str
    difficult: bool
    xmin: float
    ymin: float
    xmax: float
    ymax: float


@dataclass(frozen=True)
class Sample:
    stem: str
    source_split: str
    image: Path
    xml: Path | None
    width: int
    height: int
    boxes: tuple[Box, ...]
    sha256: str
    dhash: int
    gray: np.ndarray

    @property
    def defect(self) -> bool:
        return bool(self.boxes)

    @property
    def difficult(self) -> bool:
        return any(box.difficult for box in self.boxes)

    @property
    def all_difficult(self) -> bool:
        return bool(self.boxes) and all(box.difficult for box in self.boxes)

    @property
    def classes(self) -> tuple[str, ...]:
        return tuple(sorted({box.name for box in self.boxes}))

    @property
    def stratum(self) -> str:
        classes = "+".join(self.classes) if self.classes else "normal"
        return f"{classes}|d{int(self.difficult)}"


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left, right = self.find(left), self.find(right)
        if left == right:
            return
        if self.rank[left] < self.rank[right]:
            left, right = right, left
        self.parent[right] = left
        if self.rank[left] == self.rank[right]:
            self.rank[left] += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Missing Hole V1 datasets")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_features(path: Path) -> tuple[int, int, int, np.ndarray]:
    with Image.open(path) as opened:
        width, height = opened.size
        gray = np.asarray(opened.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
        small = np.asarray(opened.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).ravel()
    dhash = 0
    for bit in bits:
        dhash = (dhash << 1) | int(bit)
    gray = (gray - gray.mean()) / max(float(gray.std()), 1e-6)
    return width, height, dhash, gray.ravel()


def find_image(directory: Path, stem: str) -> Path | None:
    matches = [path for path in directory.glob(f"{stem}.*") if path.suffix.lower() in IMAGE_EXTENSIONS]
    if len(matches) > 1:
        raise ValueError(f"Duplicate image stem {stem!r} in {directory}")
    return matches[0] if matches else None


def parse_xml(path: Path, width: int, height: int) -> tuple[Box, ...]:
    root = ET.parse(path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError(f"Missing size in {path}")
    xml_size = (int(size.findtext("width", "0")), int(size.findtext("height", "0")))
    if xml_size != (width, height):
        raise ValueError(f"Image/XML size mismatch {path}: image={(width, height)} xml={xml_size}")
    boxes: list[Box] = []
    for obj in root.findall("object"):
        name = obj.findtext("name", "").strip()
        if name not in {"bottom", "oblique", "side"}:
            raise ValueError(f"Unexpected class {name!r} in {path}")
        difficult_text = obj.findtext("difficult", "0").strip()
        if difficult_text not in {"0", "1"}:
            raise ValueError(f"Invalid difficult={difficult_text!r} in {path}")
        node = obj.find("bndbox")
        if node is None:
            raise ValueError(f"Missing bndbox in {path}")
        values = tuple(float(node.findtext(key, "nan")) for key in ("xmin", "ymin", "xmax", "ymax"))
        xmin, ymin, xmax, ymax = values
        if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
            raise ValueError(f"Invalid box {values} in {path}")
        boxes.append(Box(name, difficult_text == "1", xmin, ymin, xmax, ymax))
    return tuple(boxes)


def load_split(source: Path, split: str) -> list[Sample]:
    image_dir = source / "images" / f"{split}_missing_tooth"
    annotation_dir = source / "annotations" / f"{split}_missing_tooth"
    images = sorted(path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if len({path.stem for path in images}) != len(images):
        raise ValueError(f"Duplicate image stems in {image_dir}")
    samples = []
    for image in images:
        width, height, dhash, gray = image_features(image)
        xml = annotation_dir / f"{image.stem}.xml"
        boxes = parse_xml(xml, width, height) if xml.is_file() else ()
        samples.append(Sample(image.stem, split, image, xml if xml.is_file() else None, width, height, boxes, sha256(image), dhash, gray))
    image_stems = {sample.stem for sample in samples}
    orphans = [path.name for path in annotation_dir.glob("*.xml") if path.stem not in image_stems]
    if orphans:
        raise FileNotFoundError(f"XML without images in {split}: {orphans}")
    return samples


def numeric_id(stem: str) -> int | None:
    match = re.search(r"(\d+)$", stem)
    return int(match.group(1)) if match else None


def build_groups(samples: list[Sample]) -> tuple[list[list[int]], list[dict[str, object]]]:
    union = UnionFind(len(samples))
    links: list[dict[str, object]] = []
    for left in range(len(samples)):
        a = samples[left]
        for right in range(left + 1, len(samples)):
            b = samples[right]
            distance = (a.dhash ^ b.dhash).bit_count()
            exact = a.sha256 == b.sha256
            aid, bid = numeric_id(a.stem), numeric_id(b.stem)
            adjacent = aid is not None and bid is not None and abs(aid - bid) <= 2
            aspect_a, aspect_b = a.width / a.height, b.width / b.height
            aspect_close = abs(aspect_a - aspect_b) / max(aspect_a, aspect_b) <= 0.08
            correlation = float(np.dot(a.gray, b.gray) / len(a.gray)) if adjacent and aspect_close else -1.0
            reason = None
            if exact:
                reason = "sha256"
            elif distance <= 2:
                reason = f"dhash_{distance}"
            elif adjacent and aspect_close and correlation >= 0.985:
                reason = "adjacent_correlated"
            if reason:
                union.union(left, right)
                links.append({"left": a.stem, "right": b.stem, "reason": reason, "dhash_distance": distance, "correlation": correlation})
    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(samples)):
        grouped[union.find(index)].append(index)
    return list(grouped.values()), links


def stratified_group_split(samples: list[Sample], groups: list[list[int]], seed: int) -> dict[str, str]:
    total = Counter(sample.stratum for sample in samples)
    targets = {key: value * 0.20 for key, value in total.items()}
    target_total = len(samples) * 0.20
    best: tuple[float, set[int]] | None = None
    for attempt in range(2000):
        rng = random.Random(seed + attempt)
        order = list(range(len(groups)))
        rng.shuffle(order)
        chosen: set[int] = set()
        counts: Counter[str] = Counter()
        size = 0
        for group_index in order:
            group = groups[group_index]
            group_counts = Counter(samples[index].stratum for index in group)
            before = ((size - target_total) / max(1.0, target_total)) ** 2 + sum(
                ((counts[key] - target) / max(1.0, target)) ** 2 for key, target in targets.items()
            )
            after_size = size + len(group)
            after_counts = counts + group_counts
            after = ((after_size - target_total) / max(1.0, target_total)) ** 2 + sum(
                ((after_counts[key] - target) / max(1.0, target)) ** 2 for key, target in targets.items()
            )
            if after < before:
                chosen.add(group_index)
                counts = after_counts
                size = after_size
        score = abs(size - target_total) + sum(abs(counts[key] - target) for key, target in targets.items())
        if best is None or score < best[0]:
            best = (score, chosen)
    if best is None:
        raise RuntimeError("Unable to create grouped split")
    validation = {index for group_index in best[1] for index in groups[group_index]}
    return {sample.stem: ("val" if index in validation else "train") for index, sample in enumerate(samples)}


def hardlink_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def yolo_lines(sample: Sample, mapping: dict[str, int], boxes: tuple[Box, ...]) -> list[str]:
    lines = []
    for box in boxes:
        cx = (box.xmin + box.xmax) / (2 * sample.width)
        cy = (box.ymin + box.ymax) / (2 * sample.height)
        width = (box.xmax - box.xmin) / sample.width
        height = (box.ymax - box.ymin) / sample.height
        values = (cx, cy, width, height)
        if not all(0 <= value <= 1 for value in values):
            raise ValueError(f"Normalized box outside [0,1] for {sample.stem}: {values}")
        lines.append(f"{mapping[box.name]} {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}")
    return lines


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def materialize_variants(samples: list[Sample], split_map: dict[str, str], output: Path) -> dict[str, object]:
    reports: dict[str, object] = {}
    link_modes: Counter[str] = Counter()
    for scheme, (mapping, names) in CLASS_SCHEMES.items():
        for policy in ("include_difficult", "exclude_difficult"):
            root = output / "yolo" / f"{scheme}_{policy}"
            manifest_rows: list[dict[str, object]] = []
            for sample in samples:
                split = "test" if sample.source_split == "test" else split_map[sample.stem]
                boxes = sample.boxes
                excluded = False
                reason = ""
                if policy == "exclude_difficult" and split == "train":
                    boxes = tuple(box for box in boxes if not box.difficult)
                    if sample.boxes and not boxes:
                        excluded, reason = True, "all_boxes_difficult"
                if excluded:
                    manifest_rows.append({"stem": sample.stem, "split": split, "defect": int(sample.defect), "boxes": len(sample.boxes), "kept_boxes": 0, "difficult_boxes": sum(box.difficult for box in sample.boxes), "excluded": 1, "reason": reason, "image": sample.image, "xml": sample.xml or ""})
                    continue
                image_path = root / "images" / split / sample.image.name
                link_modes[hardlink_or_copy(sample.image, image_path)] += 1
                label_path = root / "labels" / split / f"{sample.stem}.txt"
                label_path.parent.mkdir(parents=True, exist_ok=True)
                lines = yolo_lines(sample, mapping, boxes)
                label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")
                manifest_rows.append({"stem": sample.stem, "split": split, "defect": int(sample.defect), "boxes": len(sample.boxes), "kept_boxes": len(boxes), "difficult_boxes": sum(box.difficult for box in sample.boxes), "excluded": 0, "reason": "", "image": sample.image, "xml": sample.xml or ""})
            yaml = [f"path: {root.as_posix()}", "train: images/train", "val: images/val", "names:"]
            yaml.extend(f"  {index}: {name}" for index, name in enumerate(names))
            (root / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="ascii")
            fields = ["stem", "split", "defect", "boxes", "kept_boxes", "difficult_boxes", "excluded", "reason", "image", "xml"]
            write_csv(root / "manifest.csv", manifest_rows, fields)
            usable = [row for row in manifest_rows if not row["excluded"]]
            reports[f"{scheme}_{policy}"] = {
                "classes": names,
                "train_images": sum(row["split"] == "train" for row in usable),
                "val_images": sum(row["split"] == "val" for row in usable),
                "test_images": sum(row["split"] == "test" for row in usable),
                "train_boxes": sum(int(row["kept_boxes"]) for row in usable if row["split"] == "train"),
                "excluded_train_images": sum(bool(row["excluded"]) for row in manifest_rows),
            }
    reports["materialization"] = dict(link_modes)
    return reports


def write_master_manifest(samples: list[Sample], split_map: dict[str, str], output: Path) -> None:
    rows = []
    for sample in samples:
        split = "test" if sample.source_split == "test" else split_map[sample.stem]
        rows.append({
            "stem": sample.stem, "source_split": sample.source_split, "split": split,
            "defect": int(sample.defect), "classes": "+".join(sample.classes), "boxes": len(sample.boxes),
            "difficult_boxes": sum(box.difficult for box in sample.boxes), "has_difficult": int(sample.difficult),
            "all_difficult": int(sample.all_difficult), "width": sample.width, "height": sample.height,
            "sha256": sample.sha256, "dhash": f"{sample.dhash:016x}", "image": sample.image, "xml": sample.xml or "",
        })
    write_csv(output / "master_manifest.csv", rows, list(rows[0]))


def validate(samples: list[Sample], split_map: dict[str, str], groups: list[list[int]], output: Path) -> dict[str, object]:
    train_pool = [sample for sample in samples if sample.source_split == "train"]
    test = [sample for sample in samples if sample.source_split == "test"]
    counts = {
        "train_pool_images": len(train_pool), "train_pool_defect_images": sum(sample.defect for sample in train_pool),
        "train_pool_boxes": sum(len(sample.boxes) for sample in train_pool),
        "train_pool_difficult_boxes": sum(box.difficult for sample in train_pool for box in sample.boxes),
        "test_images": len(test), "test_defect_images": sum(sample.defect for sample in test),
        "test_boxes": sum(len(sample.boxes) for sample in test),
        "test_difficult_boxes": sum(box.difficult for sample in test for box in sample.boxes),
    }
    expected = {"train_pool_images": 496, "train_pool_defect_images": 173, "train_pool_boxes": 614, "train_pool_difficult_boxes": 25, "test_images": 150, "test_defect_images": 44, "test_boxes": 168, "test_difficult_boxes": 6}
    if counts != expected:
        raise RuntimeError(f"Unexpected source counts: {counts}")
    membership = {}
    for group_id, group in enumerate(groups):
        splits = {split_map[train_pool[index].stem] for index in group}
        if len(splits) != 1:
            raise RuntimeError(f"Near-duplicate group crosses split: {group_id}")
        for index in group:
            membership[train_pool[index].stem] = group_id
    for variant in (output / "yolo").iterdir():
        if not variant.is_dir():
            continue
        for split in ("train", "val", "test"):
            image_stems = {path.stem for path in (variant / "images" / split).glob("*") if path.is_file()}
            label_stems = {path.stem for path in (variant / "labels" / split).glob("*.txt")}
            if image_stems != label_stems:
                raise RuntimeError(f"Image/label mismatch in {variant.name}/{split}")
            class_count = len(CLASS_SCHEMES[variant.name.split("_include_")[0].split("_exclude_")[0]][1])
            for label in (variant / "labels" / split).glob("*.txt"):
                for line in label.read_text(encoding="ascii").splitlines():
                    fields = line.split()
                    if len(fields) != 5 or not 0 <= int(fields[0]) < class_count or not all(0 <= float(value) <= 1 for value in fields[1:]):
                        raise RuntimeError(f"Invalid YOLO label in {label}: {line}")
    return {**counts, "train_images": sum(value == "train" for value in split_map.values()), "val_images": sum(value == "val" for value in split_map.values()), "near_duplicate_groups": len(groups), "status": "passed", "group_membership": membership}


def main() -> None:
    args = parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists():
        if not args.force:
            raise FileExistsError(f"Generated directory exists; use --force: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    train = load_split(source, "train")
    test = load_split(source, "test")
    groups, links = build_groups(train)
    split_map = stratified_group_split(train, groups, args.seed)
    variant_report = materialize_variants(train + test, split_map, output)
    write_master_manifest(train + test, split_map, output)
    write_csv(output / "near_duplicate_links.csv", links, ["left", "right", "reason", "dhash_distance", "correlation"])
    report = validate(train + test, split_map, groups, output)
    report["seed"] = args.seed
    report["variants"] = variant_report
    (output / "preflight_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "group_membership"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
