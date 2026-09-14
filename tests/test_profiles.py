import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gp.config import AppConfig
from gp.profiles import ProfileError, apply_to_config, mission_utility


class ProfileTests(unittest.TestCase):
    def test_sparse_changes_interval(self):
        config = AppConfig()
        plan = apply_to_config(config, "SPARSE")
        self.assertEqual(config.inference_profile, "SPARSE")
        self.assertEqual(config.inference_interval, 0.20)
        self.assertFalse(plan["stop_worker"])
        self.assertFalse(plan["start_worker"])

    def test_safe_stop_requests_worker_stop(self):
        config = AppConfig()
        plan = apply_to_config(config, "SAFE_STOP")
        self.assertEqual(config.inference_profile, "SAFE_STOP")
        self.assertTrue(plan["stop_worker"])
        self.assertFalse(plan["start_worker"])

    def test_full_after_safe_stop_requests_start(self):
        config = AppConfig()
        apply_to_config(config, "SAFE_STOP")
        plan = apply_to_config(config, "FULL")
        self.assertEqual(config.inference_interval, 0.10)
        self.assertTrue(plan["start_worker"])

    def test_unimplemented_profile_errors(self):
        config = AppConfig()
        with self.assertRaises(ProfileError):
            apply_to_config(config, "CLASSIFY_ONLY")
        with self.assertRaises(ProfileError):
            apply_to_config(config, "LOCATE_ONLY")
        self.assertEqual(config.inference_profile, "FULL")

    def test_trt_fast_requires_engine_file(self):
        config = AppConfig()
        with self.assertRaises(ProfileError):
            apply_to_config(config, "TRT_FAST")
        self.assertEqual(config.inference_profile, "FULL")

    def test_trt_fast_rebuilds_when_engine_exists(self):
        import hashlib
        import json

        config = AppConfig()
        with tempfile.TemporaryDirectory() as tmp:
            engine = Path(tmp) / "model1.engine"
            engine.write_bytes(b"x")
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(
                json.dumps({"engine": {"sha256": hashlib.sha256(b"x").hexdigest()}}),
                encoding="utf-8",
            )
            with patch("gp.profiles.ENGINE_LOCATOR", engine), patch("gp.profiles.ENGINE_MANIFEST", manifest):
                plan = apply_to_config(config, "TRT_FAST")
            self.assertTrue(plan["rebuild_inspector"])
            self.assertEqual(Path(config.locator_model), engine)
            self.assertEqual(config.inference_profile, "TRT_FAST")

    def test_mission_utility(self):
        self.assertEqual(mission_utility("FULL", True, True), 1.0)
        self.assertEqual(mission_utility("SPARSE", True, True), 0.95)
        self.assertEqual(mission_utility("SAFE_STOP", False, True), 0.2)
        self.assertEqual(mission_utility("TRT_FAST", True, True), 1.0)
        self.assertEqual(mission_utility("SPARSE", True, True, valid_output_ratio=0.5), 0.725)
