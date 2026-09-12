import unittest

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
            apply_to_config(config, "TRT_FAST")
        with self.assertRaises(ProfileError):
            apply_to_config(config, "CLASSIFY_ONLY")
        self.assertEqual(config.inference_profile, "FULL")

    def test_mission_utility(self):
        self.assertEqual(mission_utility("FULL", True, True), 1.0)
        self.assertEqual(mission_utility("SPARSE", True, True), 0.95)
        self.assertEqual(mission_utility("SAFE_STOP", False, True), 0.2)
        self.assertIsNone(mission_utility("TRT_FAST", True, True))
