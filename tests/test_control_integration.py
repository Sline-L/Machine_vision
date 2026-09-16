"""Control + Guardian integration tests that do not load YOLO weights."""

import unittest

from gp.actions import accept
from gp.config import AppConfig
from gp.control import ControlService
from gp.control_view import as_control_view, cap_verify_level
from gp.guardian import thermal_stop_needed
from gp.runtime import GearProRuntime
from gp.telemetry import build_snapshot
from gp.types import GearObservation, InspectionResult


def _v1_snapshot(**overrides):
    data = {
        "schema_version": "system-snapshot.v1",
        "system": {},
        "camera": {"opened": True, "frame_age_ms": 40, "read_failures": 0},
        "locator": {},
        "scratch_v5": {"error_count": 0, "total_latency_ms": 50.0},
        "serial": {"connected": True, "consecutive_failures": 0},
        "mission": {"inspection_active": False, "current_profile": "SAFE_STOP"},
    }
    data.update(overrides)
    return data


class ControlViewTests(unittest.TestCase):
    def test_v2_health_is_not_relabeled_as_v2_when_adapted(self):
        config = AppConfig()
        result = InspectionResult(
            None,
            [
                GearObservation(
                    (0, 0, 1, 1), 0.9, 0.1,
                    scratch_reject=False,
                    missing_hole_reject=False,
                )
            ],
            scratch_latency_ms=40,
            missing_hole_latency_ms=50,
        )
        health = build_snapshot(
            config, None, True, "/dev/video0", 0, 30.0, None,
            last_result=result,
            inspection_active=True,
            schema_version="system-snapshot.v2",
        )
        self.assertEqual(health["schema_version"], "system-snapshot.v2")
        self.assertIn("specialists", health)
        view = as_control_view(health)
        self.assertEqual(view["schema_version"], "gearpro-control-view.v1")
        self.assertIn("scratch_v5", view)
        self.assertFalse(view["control_view"]["dual_specialist_mission_verified"])
        self.assertEqual(health["schema_version"], "system-snapshot.v2")

    def test_resume_is_not_marked_recovered(self):
        level, note = cap_verify_level("resume_inspection", {}, "mission")
        self.assertEqual(level, "config")
        self.assertIn("6.3", note)
        level, note = cap_verify_level("set_inference_profile", {"profile": "SAFE_STOP"}, "mission")
        self.assertEqual(level, "mission")
        self.assertIsNone(note)


class EmergencyHoldTests(unittest.TestCase):
    def test_thermal_predicate(self):
        self.assertTrue(thermal_stop_needed({"system": {"temperature_c": 81}}, "FULL"))
        self.assertFalse(thermal_stop_needed({"system": {"temperature_c": 81}}, "SAFE_STOP"))
        self.assertFalse(thermal_stop_needed({"system": {"temperature_c": None}}, "FULL"))

    def test_resume_rejected_during_hold(self):
        ok, reason = accept(
            "resume_inspection",
            {},
            _v1_snapshot(camera={"opened": True}),
            extras={"emergency_hold": True, "video_mode": False},
        )
        self.assertFalse(ok)
        self.assertIn("紧急", reason)

    def test_agent_cannot_leave_safe_stop_while_held(self):
        ok, reason = accept(
            "set_inference_profile",
            {"profile": "FULL"},
            _v1_snapshot(),
            extras={"emergency_hold": True, "thermal_stop_needed": False, "authority": "agent"},
        )
        self.assertFalse(ok)
        ok, reason = accept(
            "set_inference_profile",
            {"profile": "FULL"},
            _v1_snapshot(),
            extras={"emergency_hold": True, "thermal_stop_needed": False, "authority": "human"},
        )
        self.assertTrue(ok, reason)


class ControlServiceCapTests(unittest.TestCase):
    def test_restart_worker_does_not_claim_recovery(self):
        class _Runtime:
            def current_snapshot(self):
                return _v1_snapshot(
                    scratch_v5={"error_count": 2, "total_latency_ms": 40.0},
                    locator={"loaded": True, "latency_ms": 10.0},
                    mission={"inspection_active": True, "current_profile": "FULL", "output_valid": True},
                )

            def control_extras(self):
                return {"worker_failed": False, "inspection_can_run": True}

            def execute_action(self, name, params):
                del name, params
                return {}

        result = ControlService(_Runtime()).run_action(
            {"name": "restart_worker", "params": {}, "source": "reasoner", "request_id": "rw"},
            authority="agent",
        )
        self.assertTrue(result["accepted"])
        self.assertTrue(result["executed"])
        self.assertFalse(result["recovery_success"])
        self.assertEqual(result["verify_level"], "config")
        self.assertIn("6.3", result["error"] or "")


class RuntimeHoldTests(unittest.TestCase):
    def test_start_inspection_respects_emergency_hold(self):
        config = AppConfig()
        config.control_port = 0
        runtime = GearProRuntime(config)
        runtime.camera = type("Cam", (), {"opened": True, "error_message": "", "device_path": "x", "read_failures": 0, "actual_fps": 0})()
        runtime._emergency_hold = True
        with self.assertRaisesRegex(RuntimeError, "紧急停机"):
            runtime.start_inspection()
