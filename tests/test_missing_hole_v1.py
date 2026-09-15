from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from missing_hole_runtime import apply_rule


WORK = ROOT / "dataset_defects" / "missing_hole_v1"


class MissingHoleV1Tests(unittest.TestCase):
    def test_preflight_counts(self) -> None:
        report = json.loads((WORK / "preflight_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["train_pool_images"], 496)
        self.assertEqual(report["test_images"], 150)
        self.assertEqual(report["train_pool_boxes"], 614)
        self.assertEqual(report["test_boxes"], 168)
        self.assertEqual((report["train_images"], report["val_images"]), (397, 99))
        self.assertEqual(report["status"], "passed")

    def test_six_variants_have_matching_images_and_labels(self) -> None:
        variants = [
            WORK / "yolo" / f"{scheme}_{policy}"
            for scheme in ("three_class", "two_class", "one_class")
            for policy in ("include_difficult", "exclude_difficult")
        ]
        self.assertEqual(len(variants), 6)
        for variant in variants:
            for split in ("train", "val", "test"):
                images = {path.stem for path in (variant / "images" / split).glob("*") if path.is_file()}
                labels = {path.stem for path in (variant / "labels" / split).glob("*.txt")}
                self.assertEqual(images, labels, f"{variant.name}/{split}")

    def test_difficult_exclusion_never_creates_false_negative(self) -> None:
        variant = WORK / "yolo" / "one_class_exclude_difficult" / "manifest.csv"
        with variant.open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        excluded = [row for row in rows if row["excluded"] == "1"]
        self.assertEqual(len(excluded), 6)
        self.assertTrue(all(row["split"] == "train" and row["defect"] == "1" and row["kept_boxes"] == "0" for row in excluded))
        val = [row for row in rows if row["split"] == "val"]
        self.assertEqual(len(val), 99)
        self.assertFalse(any(row["excluded"] == "1" for row in val))

    def test_groups_do_not_cross_split(self) -> None:
        manifest = WORK / "master_manifest.csv"
        with manifest.open(encoding="utf-8-sig") as handle:
            rows = [row for row in csv.DictReader(handle) if row["source_split"] == "train"]
        report = json.loads((WORK / "preflight_report.json").read_text(encoding="utf-8"))
        groups: dict[str, set[str]] = {}
        membership = report["group_membership"]
        for row in rows:
            groups.setdefault(str(membership[row["stem"]]), set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in groups.values()))

    def test_fusion_rules(self) -> None:
        scores = {"a": [0.1, 0.8], "b": [0.3, 0.4], "d": [0.2, 0.9]}
        mean = {"type": "classifier_mean", "models": ["a", "b"]}
        self.assertEqual(apply_rule(mean, scores), [0.2, 0.6000000000000001])
        weighted = {"type": "weighted", "alpha": 0.25, "classifier": mean, "detector": "d"}
        self.assertAlmostEqual(apply_rule(weighted, scores)[1], 0.825)


if __name__ == "__main__":
    unittest.main()
