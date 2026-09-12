import os
from pathlib import Path
import unittest
from unittest.mock import patch

from gp.config import AppConfig, PROJECT_ROOT
from gp.types import GearObservation, InspectionResult, InspectionStats
from gp.weights import classifier_family, classifier_outputs


class ConfigTests(unittest.TestCase):
    def test_default_model_paths_use_project_model_directory(self):
        config = AppConfig()
        self.assertEqual(config.locator_model, PROJECT_ROOT / "model" / "model1.pt")
        self.assertEqual(config.classifier_model, PROJECT_ROOT / "model" / "model2.pt")

    def test_environment_overrides_deployment_values(self):
        with patch.dict(os.environ, {"GEARPRO_CAMERA_INDEX": "4", "GEARPRO_MODEL1": "/tmp/one.pt"}):
            config = AppConfig.from_environment()
        self.assertEqual(config.camera_index, 4)
        self.assertEqual(config.locator_model, Path("/tmp/one.pt"))


class ClassifierCheckpointTests(unittest.TestCase):
    def test_family_from_metadata_and_weight_keys(self):
        self.assertEqual(
            classifier_family({"family": "efficientnet_b0"}, {}),
            "efficientnet_b0",
        )
        self.assertEqual(classifier_family({}, {"fc.weight": object()}), "resnet18")
        self.assertEqual(
            classifier_family({}, {"classifier.1.weight": object()}),
            "efficientnet_b0",
        )

    def test_output_dim_from_head_weights(self):
        class Fake:
            def __init__(self, shape):
                self.shape = shape

        self.assertEqual(classifier_outputs({"fc.weight": Fake((1, 512))}), 1)
        self.assertEqual(classifier_outputs({"classifier.1.weight": Fake((1, 1280))}), 1)


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
