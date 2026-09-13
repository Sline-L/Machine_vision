import unittest

from gp.verify import assess, recovery_success
from gp.actions import verify


def _snapshot(**overrides):
    data = {
        "schema_version": "system-snapshot.v1",
        "system": {},
        "camera": {
            "opened": True,
            "frame_seq": 10,
            "frame_age_ms": 40,
            "read_failures": 0,
        },
        "locator": {"backend": "pt", "loaded": False, "latency_ms": None},
        "scratch_v5": {"error_count": 0, "total_latency_ms": None},
        "serial": {"connected": True, "consecutive_failures": 0},
        "mission": {"inspection_active": False, "current_profile": "FULL", "output_valid": False},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return data


class VerifyLevelTests(unittest.TestCase):
    def test_trt_without_infer_is_config_only(self):
        before = _snapshot()
        after = _snapshot(
            locator={"backend": "engine", "loaded": False, "latency_ms": None},
            mission={"inspection_active": False, "current_profile": "TRT_FAST", "output_valid": False},
        )
        level, reason = assess("set_inference_profile", {"profile": "TRT_FAST"}, before, after, {})
        self.assertEqual(level, "config", reason)
        self.assertFalse(recovery_success(level))
        ok, _reason = verify("set_inference_profile", {"profile": "TRT_FAST"}, before, after, {})
        self.assertTrue(ok)

    def test_infer_promotes_to_function(self):
        before = _snapshot()
        after = _snapshot(
            locator={"backend": "engine", "loaded": True, "latency_ms": 22.0},
            scratch_v5={"error_count": 0, "total_latency_ms": 70.0},
            mission={"inspection_active": True, "current_profile": "TRT_FAST", "output_valid": True},
        )
        level, reason = assess(
            "set_locator_profile",
            {"profile": "trt_fast"},
            before,
            after,
            {"inspection_can_run": True},
        )
        self.assertEqual(level, "function", reason)
        self.assertTrue(recovery_success(level))

    def test_safe_stop_is_function(self):
        before = _snapshot(mission={"inspection_active": True, "current_profile": "FULL"})
        after = _snapshot(mission={"inspection_active": False, "current_profile": "SAFE_STOP"})
        level, reason = assess("set_inference_profile", {"profile": "SAFE_STOP"}, before, after, {})
        self.assertEqual(level, "function", reason)


if __name__ == "__main__":
    unittest.main()
