import unittest

from edgemedic.policy import Memory, decide
from gp.guardian import thermal_stop_needed


def _snap(**kwargs):
    data = {
        "system": {"temperature_c": 55.0},
        "camera": {"opened": True, "frame_seq": 10, "frame_age_ms": 40, "read_failures": 0},
        "locator": {"latency_ms": 18.0},
        "scratch_v5": {"error_count": 0, "total_latency_ms": 50.0},
        "serial": {"connected": True, "consecutive_failures": 0, "health": 1.0},
        "mission": {"inspection_active": True, "current_profile": "FULL"},
    }
    for key, value in kwargs.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return data


class GuardianTests(unittest.TestCase):
    def test_thermal_stop_threshold(self):
        self.assertTrue(thermal_stop_needed({"system": {"temperature_c": 81}}, "FULL"))
        self.assertFalse(thermal_stop_needed({"system": {"temperature_c": 81}}, "SAFE_STOP"))
        self.assertFalse(thermal_stop_needed({"system": {"temperature_c": None}}, "FULL"))


class ReflexPolicyTests(unittest.TestCase):
    def test_healthy_snapshot_is_idle(self):
        self.assertIsNone(decide(_snap()))

    def test_thermal_beats_camera_stale(self):
        action = decide(_snap(system={"temperature_c": 85.0}, camera={"opened": False}))
        self.assertEqual(action["layer"], "L0")
        self.assertEqual(action["params"]["profile"], "SAFE_STOP")

    def test_stale_camera_restarts(self):
        action = decide(_snap(camera={"frame_age_ms": 1500}))
        self.assertEqual(action["name"], "restart_camera")
        self.assertEqual(action["rule"], "CAMERA_STALE")

    def test_video_mode_skips_closed_camera(self):
        action = decide(_snap(camera={"opened": False}, mission={"inspection_active": True, "current_profile": "FULL"}))
        self.assertIsNone(action)

    def test_worker_error_increase_restarts(self):
        memory = Memory()
        self.assertIsNone(decide(_snap(scratch_v5={"error_count": 0}), memory))
        action = decide(_snap(scratch_v5={"error_count": 2}), memory)
        self.assertEqual(action["name"], "restart_worker")

    def test_overload_switches_sparse(self):
        action = decide(_snap(scratch_v5={"total_latency_ms": 240.0}))
        self.assertEqual(action["name"], "set_inference_profile")
        self.assertEqual(action["params"]["profile"], "SPARSE")

    def test_safe_stop_does_not_auto_resume(self):
        action = decide(
            _snap(
                mission={"inspection_active": False, "current_profile": "SAFE_STOP"},
                camera={"frame_age_ms": 2000},
            )
        )
        self.assertIsNone(action)

    def test_serial_failure_reconnects(self):
        action = decide(_snap(serial={"connected": False, "consecutive_failures": 2, "health": 0.4}))
        self.assertEqual(action["name"], "reconnect_serial")


if __name__ == "__main__":
    unittest.main()
