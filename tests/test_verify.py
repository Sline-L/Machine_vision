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
            scratch_v5={"error_count": 0, "total_latency_ms": 70.0, "loaded": True, "last_valid_output": True},
            missing_hole_v1={"total_latency_ms": 55.0, "loaded": True, "last_valid_output": True},
            mission={"inspection_active": True, "current_profile": "TRT_FAST", "output_valid": True},
        )
        level, reason = assess(
            "set_locator_profile",
            {"profile": "trt_fast"},
            before,
            after,
            {"inspection_can_run": True, "dual_specialist_evidence": True, "output_fresh": True},
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
            scratch_v5={"error_count": 0, "total_latency_ms": 60.0, "loaded": True, "last_valid_output": True},
            missing_hole_v1={"total_latency_ms": 50.0, "loaded": True, "last_valid_output": True},
            camera={"opened": True, "frame_seq": 20, "frame_age_ms": 40, "health": 1.0},
            mission={"inspection_active": True, "current_profile": "SPARSE", "output_valid": True, "utility": 0.95},
        )
        extras = {
            "inspection_can_run": True,
            "dual_specialist_evidence": True,
            "output_fresh": True,
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
            scratch_v5={"error_count": 0, "total_latency_ms": 60.0, "loaded": True, "last_valid_output": True},
            missing_hole_v1={"total_latency_ms": 50.0, "loaded": True, "last_valid_output": True},
            camera={"health": 1.0},
            mission={"inspection_active": True, "current_profile": "SPARSE", "output_valid": True, "utility": 0.95},
        )
        extras = {
            "inspection_can_run": True,
            "dual_specialist_evidence": True,
            "output_fresh": True,
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
            scratch_v5={"error_count": 0, "total_latency_ms": 60.0, "loaded": True, "last_valid_output": True},
            missing_hole_v1={"total_latency_ms": 50.0, "loaded": True, "last_valid_output": True},
            camera={"health": 1.0},
            mission={"inspection_active": True, "current_profile": "SPARSE", "output_valid": True, "utility": 0.95},
        )
        extras = {
            "inspection_can_run": True,
            "dual_specialist_evidence": True,
            "output_fresh": True,
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


class DualSpecialistVerifyTests(unittest.TestCase):
    def test_scratch_only_is_not_recovery(self):
        before = _snapshot()
        after = _snapshot(
            scratch_v5={"loaded": True, "total_latency_ms": 40.0, "last_valid_output": True},
            missing_hole_v1={"loaded": False, "total_latency_ms": None, "last_valid_output": False},
            mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True},
        )
        extras = {"worker_failed": False, "output_fresh": True, "inspection_can_run": True}
        level, reason = assess("restart_worker", {}, before, after, extras)
        self.assertEqual(level, "none", reason)
        self.assertFalse(recovery_success(level))

    def test_missing_only_is_not_recovery(self):
        before = _snapshot()
        after = _snapshot(
            scratch_v5={"loaded": False, "total_latency_ms": None, "last_valid_output": False},
            missing_hole_v1={"loaded": True, "total_latency_ms": 40.0, "last_valid_output": True},
            mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True},
        )
        level, reason = assess("restart_worker", {}, before, after, {"output_fresh": True, "inspection_can_run": True})
        self.assertEqual(level, "none", reason)

    def test_both_loaded_without_fresh_output_stays_config(self):
        before = _snapshot()
        after = _snapshot(
            scratch_v5={"loaded": True, "total_latency_ms": 40.0, "last_valid_output": True},
            missing_hole_v1={"loaded": True, "total_latency_ms": 50.0, "last_valid_output": True},
            mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True},
        )
        extras = {"output_fresh": False, "inspection_can_run": True, "dual_specialist_evidence": False}
        level, reason = assess("restart_worker", {}, before, after, extras)
        self.assertEqual(level, "config", reason)

    def test_both_fresh_reaches_function(self):
        before = _snapshot()
        after = _snapshot(
            locator={"loaded": True, "latency_ms": 12.0},
            scratch_v5={"loaded": True, "total_latency_ms": 40.0, "last_valid_output": True},
            missing_hole_v1={"loaded": True, "total_latency_ms": 50.0, "last_valid_output": True},
            mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True, "utility": 0.8},
        )
        extras = {"output_fresh": True, "dual_specialist_evidence": True, "inspection_can_run": True}
        level, reason = assess("restart_worker", {}, before, after, extras)
        self.assertEqual(level, "function", reason)

    def test_hold_interrupts_resume_verify(self):
        after = _snapshot(mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True})
        level, reason = assess("resume_inspection", {}, _snapshot(), after, {"emergency_hold": True})
        self.assertEqual(level, "none", reason)

    def test_pause_is_stop_not_inspection_recovery(self):
        after = _snapshot(mission={"inspection_active": False, "current_profile": "FULL"})
        level, reason = assess("pause_inspection", {}, _snapshot(), after, {})
        self.assertEqual(level, "mission", reason)

    def test_safe_stop_mission_is_not_dual_recovery_claim(self):
        from gp.control_view import inspection_recovery_success

        after = _snapshot(mission={"inspection_active": False, "current_profile": "SAFE_STOP"})
        level, reason = assess("set_inference_profile", {"profile": "SAFE_STOP"}, _snapshot(), after, {})
        self.assertEqual(level, "mission", reason)
        self.assertFalse(inspection_recovery_success("set_inference_profile", {"profile": "SAFE_STOP"}, level, {}))

    def test_apply_settings_stays_config(self):
        extras = {"settings": {"stream_fps": 8.0}}
        level, reason = assess("apply_settings", {"stream_fps": 8.0}, _snapshot(), _snapshot(), extras)
        self.assertEqual(level, "config", reason)

    def test_accepted_hold_cannot_promote(self):
        after = _snapshot(
            scratch_v5={"loaded": True, "total_latency_ms": 40.0, "last_valid_output": True},
            missing_hole_v1={"loaded": True, "total_latency_ms": 50.0, "last_valid_output": True},
            mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True},
        )
        extras = {"emergency_hold": True, "dual_specialist_evidence": True, "output_fresh": True, "inspection_can_run": True}
        level, reason = assess("restart_worker", {}, _snapshot(), after, extras)
        self.assertEqual(level, "none", reason)


if __name__ == "__main__":
    unittest.main()
