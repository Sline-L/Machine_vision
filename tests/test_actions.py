import unittest
from pathlib import Path
from unittest.mock import patch

from gp.actions import ActionError, accept, parse_request, verify


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
        "locator": {},
        "scratch_v5": {"error_count": 0},
        "serial": {"connected": True, "consecutive_failures": 0},
        "mission": {"inspection_active": True, "current_profile": "FULL"},
    }
    data.update(overrides)
    return data


class ActionContractTests(unittest.TestCase):
    def test_parse_rejects_unknown_name(self):
        with self.assertRaises(ActionError):
            parse_request({"name": "reboot", "params": {}, "source": "human", "request_id": "1"})

    def test_locator_profile_needs_engine_file(self):
        with patch("gp.profiles.ENGINE_LOCATOR", Path("/no/such/model1.engine")):
            ok, reason = accept("set_locator_profile", {"profile": "trt_fast"}, _snapshot())
        self.assertFalse(ok)
        self.assertIn("找不到", reason)

    def test_rollback_needs_backup(self):
        ok, reason = accept("rollback_config", {}, _snapshot(), extras={})
        self.assertFalse(ok)
        self.assertIn("回滚", reason)
        ok, reason = accept("rollback_config", {}, _snapshot(), extras={"config_backup": True})
        self.assertTrue(ok, reason)

    def test_verify_locator_backend(self):
        before = _snapshot()
        after = _snapshot(locator={"backend": "engine", "loaded": True})
        ok, reason = verify(
            "set_locator_profile",
            {"profile": "trt_fast"},
            before,
            after,
            extras={"inspection_should_run": True},
        )
        self.assertTrue(ok, reason)

    def test_trt_fast_rejected_without_engine(self):
        with patch("gp.profiles.ENGINE_LOCATOR", Path("/no/such/model1.engine")):
            ok, reason = accept("set_inference_profile", {"profile": "TRT_FAST"}, _snapshot())
        self.assertFalse(ok)
        self.assertIn("engine", reason)
        ok, reason = accept("set_inference_profile", {"profile": "CLASSIFY_ONLY"}, _snapshot())
        self.assertFalse(ok)
        self.assertIn("尚未实现", reason)

    def test_healthy_camera_rejects_restart(self):
        ok, _reason = accept("restart_camera", {}, _snapshot())
        self.assertFalse(ok)

    def test_stale_camera_allows_restart(self):
        snap = _snapshot(camera={"opened": True, "frame_seq": 10, "frame_age_ms": 1500, "read_failures": 0})
        ok, reason = accept("restart_camera", {}, snap)
        self.assertTrue(ok, reason)

    def test_pause_requires_active_inspection(self):
        snap = _snapshot(mission={"inspection_active": False, "current_profile": "FULL"})
        ok, _reason = accept("pause_inspection", {}, snap)
        self.assertFalse(ok)

    def test_verify_profile_change(self):
        before = _snapshot()
        after = _snapshot(mission={"inspection_active": True, "current_profile": "SPARSE"})
        ok, reason = verify("set_inference_profile", {"profile": "SPARSE"}, before, after)
        self.assertTrue(ok, reason)

    def test_verify_get_state_needs_keys(self):
        ok, _reason = verify("get_state", {}, {}, {"camera": {}}, {})
        self.assertFalse(ok)
        ok, reason = verify("get_state", {}, {}, _snapshot(), {})
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main()
