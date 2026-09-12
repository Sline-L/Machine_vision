import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gp.config import AppConfig, PROJECT_ROOT
from gp.export_engine import DEFAULT_DEST, DEFAULT_SOURCE
from gp.launch import EXPORTS, start
from gp.models import TwoStageInspector
from gp.scratch_v5 import (
    ScratchV5Runtime,
    apply_temperature,
    fuse_probabilities,
    load_model2_config,
    square_rgb_image,
)
from gp.types import GearObservation, InspectionResult, InspectionStats


class ConfigTests(unittest.TestCase):
    def test_default_model_paths_use_project_model_directory(self):
        config = AppConfig()
        self.assertEqual(config.locator_model, PROJECT_ROOT / "model" / "model1.pt")
        self.assertEqual(config.model2_config, PROJECT_ROOT / "model" / "model2" / "inference_config.json")
        self.assertAlmostEqual(config.defect_threshold, 0.300273610279458)

    def test_environment_overrides_deployment_values(self):
        with patch.dict(
            os.environ,
            {"GEARPRO_CAMERA_INDEX": "4", "GEARPRO_MODEL1": "/tmp/one.pt", "GEARPRO_MODEL2": "/tmp/two.json"},
        ):
            config = AppConfig.from_environment()
        self.assertEqual(config.camera_index, 4)
        self.assertEqual(config.locator_model, Path("/tmp/one.pt"))
        self.assertEqual(config.model2_config, Path("/tmp/two.json"))

    def test_model2_config_supplies_default_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model2.json"
            path.write_text(json.dumps({"default_threshold": 0.412345}), encoding="utf-8")
            with patch.dict(os.environ, {"GEARPRO_MODEL2": str(path)}):
                config = AppConfig.from_environment()
        self.assertAlmostEqual(config.defect_threshold, 0.412345)

    def test_missing_locator_file_stops_before_qt(self):
        self.assertEqual(start(locator=EXPORTS / "missing.engine"), 1)

    def test_engine_export_writes_cache_artifact(self):
        self.assertEqual(DEFAULT_SOURCE, PROJECT_ROOT / "model" / "model1.pt")
        self.assertEqual(DEFAULT_DEST, EXPORTS / "model1.engine")


class ScratchV5Tests(unittest.TestCase):
    def test_temperature_and_weighted_fusion(self):
        self.assertAlmostEqual(apply_temperature(0.5, 2.0), 0.5)
        fused, classifiers = fuse_probabilities(0.2, 0.4, 0.8, alpha=0.25)
        self.assertAlmostEqual(classifiers, 0.3)
        self.assertAlmostEqual(fused, 0.675)

    def test_square_image_preserves_aspect_ratio_and_gray_padding(self):
        import numpy as np

        source = np.zeros((20, 40, 3), dtype=np.uint8)
        source[:, :] = (10, 20, 30)
        image = np.asarray(square_rgb_image(source, 100))
        self.assertEqual(image.shape, (100, 100, 3))
        self.assertEqual(tuple(image[0, 0]), (238, 238, 238))
        self.assertEqual(tuple(image[50, 50]), (10, 20, 30))

    def test_config_resolves_relative_weights_and_checks_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = []
            for name in ("one.pt", "two.pt", "detector.pt"):
                path = root / name
                path.write_bytes(name.encode())
                weights.append((name, hashlib.sha256(name.encode()).hexdigest()))
            config = {
                "version": "scratch_v5",
                "classifiers": [
                    {
                        "name": "one", "family": "efficientnet_b0", "weights": weights[0][0],
                        "sha256": weights[0][1], "imgsz": 384, "tta": "none", "temperature": 0.7,
                    },
                    {
                        "name": "two", "family": "resnet18", "weights": weights[1][0],
                        "sha256": weights[1][1], "imgsz": 384, "tta": "none", "temperature": 2.05,
                    },
                ],
                "detector": {
                    "weights": weights[2][0], "sha256": weights[2][1], "imgsz": 960,
                    "temperature": 2.125, "conf_floor": 0.001, "iou": 0.7,
                },
                "fusion": {
                    "type": "weighted",
                    "alpha": 0.25,
                    "classifier": {"type": "classifier_mean", "models": ["one", "two"]},
                },
                "default_threshold": 0.3,
            }
            config_path = root / "inference_config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_model2_config(config_path)
            self.assertEqual(loaded["classifiers"][0]["weights"], root / "one.pt")
            config["detector"]["sha256"] = "0" * 64
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "权重校验失败"):
                load_model2_config(config_path)

    def test_real_model_bundle_loads_on_cpu(self):
        runtime = ScratchV5Runtime(
            PROJECT_ROOT / "model" / "model2" / "inference_config.json",
            device="cpu",
            warmup=False,
        )
        self.assertEqual(runtime.version, "scratch_v5")
        self.assertEqual(len(runtime.classifiers), 2)
        self.assertEqual(set(runtime.detector.names.values()), {"scratch"})

    def test_auxiliary_box_maps_from_roi_to_full_frame(self):
        self.assertEqual(
            TwoStageInspector._map_auxiliary_box((2, 3, 12, 13), (100, 200, 300, 400)),
            (102, 203, 112, 213),
        )
        self.assertIsNone(TwoStageInspector._map_auxiliary_box(None, (0, 0, 10, 10)))


class ResultTests(unittest.TestCase):
    def test_defect_threshold_controls_verdict(self):
        observation = GearObservation((0, 0, 10, 10), 0.9, 0.6)
        good = InspectionResult(None, [observation], defect_threshold=0.7)
        bad = InspectionResult(None, [observation], defect_threshold=0.5)
        self.assertEqual(good.verdict, "合格")
        self.assertEqual(bad.verdict, "不合格")

    def test_stats_count_and_clear(self):
        stats = InspectionStats()
        stats.add(False)
        stats.add(True)
        self.assertEqual((stats.total, stats.good, stats.defective), (2, 1, 1))
        stats.clear()
        self.assertEqual((stats.total, stats.good, stats.defective), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
