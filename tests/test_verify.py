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

    def test_safe_stop_counts_as_mission(self):
        before = _snapshot(mission={"inspection_active": True, "current_profile": "FULL"})
        after = _snapshot(mission={"inspection_active": False, "current_profile": "SAFE_STOP"})
        level, reason = assess("set_inference_profile", {"profile": "SAFE_STOP"}, before, after, {})
        self.assertEqual(level, "mission", reason)

    def test_window_promotes_sparse_to_mission(self):
        before = _snapshot(mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True})
        after = _snapshot(
            locator={"backend": "pt", "loaded": True, "latency_ms": 20.0, "health": 1.0},
            scratch_v5={"error_count": 0, "total_latency_ms": 60.0},
            camera={"opened": True, "frame_seq": 20, "frame_age_ms": 40, "health": 1.0},
            mission={"inspection_active": True, "current_profile": "SPARSE", "output_valid": True, "utility": 0.95},
        )
        extras = {
            "inspection_can_run": True,
            "camera_health": 1.0,
            "window_elapsed_s": 10.0,
            "window_stats": {
                "n": 8,
                "output_valid_ratio": 1.0,
                "locator_p95_ms": 24.0,
                "v5_p95_ms": 70.0,
                "elapsed_p95_ms": 90.0,
            },
        }
        level, reason = assess("set_inference_profile", {"profile": "SPARSE"}, before, after, extras)
        self.assertEqual(level, "mission", reason)

    def test_p95_spike_stays_function(self):
        from gp.verify import percentile

        self.assertEqual(percentile([10, 12, 11, 400, 13], 95), 400.0)
        before = _snapshot()
        after = _snapshot(
            locator={"backend": "pt", "loaded": True, "latency_ms": 20.0, "health": 1.0},
            scratch_v5={"error_count": 0, "total_latency_ms": 60.0},
            camera={"health": 1.0},
            mission={"inspection_active": True, "current_profile": "SPARSE", "output_valid": True, "utility": 0.95},
        )
        extras = {
            "inspection_can_run": True,
            "camera_health": 1.0,
            "window_elapsed_s": 10.0,
            "window_stats": {
                "n": 8,
                "output_valid_ratio": 1.0,
                "locator_p95_ms": 24.0,
                "v5_p95_ms": 400.0,
                "elapsed_p95_ms": 430.0,
            },
        }
        level, reason = assess("set_inference_profile", {"profile": "SPARSE"}, before, after, extras)
        self.assertEqual(level, "function", reason)


    def test_short_window_stays_function(self):
        before = _snapshot()
        after = _snapshot(
            locator={"backend": "pt", "loaded": True, "latency_ms": 20.0, "health": 1.0},
            scratch_v5={"error_count": 0, "total_latency_ms": 60.0},
            camera={"health": 1.0},
            mission={"inspection_active": True, "current_profile": "SPARSE", "output_valid": True, "utility": 0.95},
        )
        extras = {
            "inspection_can_run": True,
            "camera_health": 1.0,
            "window_elapsed_s": 1.0,
            "window_stats": {
                "n": 8,
                "output_valid_ratio": 1.0,
                "locator_p95_ms": 24.0,
                "v5_p95_ms": 70.0,
                "elapsed_p95_ms": 90.0,
            },
        }
        level, reason = assess("set_inference_profile", {"profile": "SPARSE"}, before, after, extras)
        self.assertEqual(level, "function", reason)
        self.assertIn("观察窗口", reason)


if __name__ == "__main__":
    unittest.main()
