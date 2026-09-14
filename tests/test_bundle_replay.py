import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from gp.app import build_parser
from gp.bundle import BundleError, load_runtime_bundle
from gp.config import AppConfig
from gp.frames import LatestFrame
from gp.replay import ReplayCapture, list_replay_images
from gp.scratch_v5 import load_model2_config


def _write_v5_bundle(root, with_manifest=True, locked=True):
    weights = []
    for name in ("classifier_1.pt", "classifier_2.pt", "detector.pt"):
        path = root / name
        path.write_bytes(name.encode())
        weights.append((name, hashlib.sha256(name.encode()).hexdigest()))
    config = {
        "version": "scratch_v5",
        "classifiers": [
            {
                "name": "one",
                "family": "efficientnet_b0",
                "weights": weights[0][0],
                "sha256": weights[0][1],
                "imgsz": 384,
                "tta": "none",
                "temperature": 0.7,
            },
            {
                "name": "two",
                "family": "resnet18",
                "weights": weights[1][0],
                "sha256": weights[1][1],
                "imgsz": 384,
                "tta": "none",
                "temperature": 2.05,
            },
        ],
        "detector": {
            "weights": weights[2][0],
            "sha256": weights[2][1],
            "imgsz": 960,
            "temperature": 2.125,
            "conf_floor": 0.001,
            "iou": 0.7,
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
    if with_manifest:
        manifest = {
            "schema_version": "runtime-bundle.v1",
            "bundle_id": "scratch-v5-test",
            "task": "scratch_detection",
            "model_family": "scratch_v5",
            "artifacts": {
                weights[0][0]: {"sha256": weights[0][1]},
                weights[1][0]: {"sha256": weights[1][1]},
                weights[2][0]: {"sha256": weights[2][1]},
            },
            "evaluation": {
                "validation": {"recall": 0.97, "fpr": 0.08, "blind": False},
                "locked_test": {"set": "test_scratch", "recall": 0.80, "fpr": 0.16, "locked": locked},
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return config_path


class BundleContractTests(unittest.TestCase):
    def test_manifest_is_optional_but_validated_when_present(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = _write_v5_bundle(root, with_manifest=False)
            loaded = load_runtime_bundle(config_path)
            self.assertIsNone(loaded["manifest"])
            _write_v5_bundle(root, with_manifest=True)
            bundled = load_runtime_bundle(config_path, require_manifest=True)
            self.assertEqual(bundled["bundle_id"], "scratch-v5-test")
            self.assertFalse(bundled["manifest"]["evaluation"]["validation"]["blind"])
            self.assertTrue(bundled["manifest"]["evaluation"]["locked_test"]["locked"])

    def test_rejects_unlocked_locked_test_and_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = _write_v5_bundle(root, locked=False)
            with self.assertRaisesRegex(BundleError, "locked_test"):
                load_runtime_bundle(config_path)
            config_path = _write_v5_bundle(root, locked=True)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            manifest["artifacts"]["classifier_1.pt"]["sha256"] = "ab" * 32
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(BundleError, "SHA"):
                load_runtime_bundle(config_path)

    def test_shipped_model2_manifest_matches_config(self):
        from gp.config import PROJECT_ROOT

        bundled = load_runtime_bundle(PROJECT_ROOT / "model" / "model2" / "inference_config.json", require_manifest=True)
        self.assertEqual(bundled["model_family"], "scratch_v5")
        self.assertEqual(bundled["manifest"]["evaluation"]["locked_test"]["set"], "test_scratch")
        load_model2_config(PROJECT_ROOT / "model" / "model2" / "inference_config.json")


class ReplayCaptureTests(unittest.TestCase):
    def test_publishes_dataset_frames_without_a_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(2):
                path = root / f"frame_{index}.png"
                image = np.full((8, 8, 3), index * 40, dtype=np.uint8)
                import cv2

                self.assertTrue(cv2.imwrite(str(path), image))
            self.assertEqual(len(list_replay_images(root)), 2)
            config = AppConfig()
            config.replay_dir = root
            config.camera_fps = 30
            store = LatestFrame()
            capture = ReplayCapture(config, store)
            self.assertTrue(capture.start())
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and store.read().sequence < 2:
                time.sleep(0.02)
            packet = store.read()
            capture.stop()
            self.assertGreaterEqual(packet.sequence, 2)
            self.assertTrue(capture.device_path.startswith("replay:"))

    def test_cli_replay_flag(self):
        args = build_parser().parse_args(["--replay", "tests/replay", "--replay-once"])
        self.assertEqual(Path(args.replay), Path("tests/replay"))
        self.assertTrue(args.replay_once)
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--replay", "tests/replay", "--video", "x.mp4"])


if __name__ == "__main__":
    unittest.main()
