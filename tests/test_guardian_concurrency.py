"""Guardian vs Control concurrency: Event-gated, not sleep-based."""

import threading
import time
import unittest

from gp.config import AppConfig
from gp.runtime import GearProRuntime


def _runtime():
    config = AppConfig()
    config.control_port = 0
    runtime = GearProRuntime(config)
    runtime.config.persist = lambda: None
    runtime.camera = type(
        "Cam",
        (),
        {"opened": True, "error_message": "", "device_path": "x", "read_failures": 0, "actual_fps": 0},
    )()
    return runtime


class GuardianConcurrencyTests(unittest.TestCase):
    def test_hold_during_rebuild_wins_and_does_not_wait_on_action_lock(self):
        runtime = _runtime()
        entered = threading.Event()
        proceed = threading.Event()

        def gated_drop():
            entered.set()
            self.assertTrue(proceed.wait(3), "rebuild did not reach gate")
            runtime.worker._inspector = None
            runtime.worker.load_status = {
                "locator": "unknown",
                "scratch_v5": "unknown",
                "missing_hole_v1": "unknown",
            }

        runtime.worker.drop_inspector = gated_drop
        runtime.config.validate_models = lambda: None
        errors = []

        def rebuild():
            try:
                with runtime._action_lock:
                    runtime.rebuild_inspector(resume=True)
            except Exception as exc:
                errors.append(str(exc))

        worker = threading.Thread(target=rebuild, name="rebuild")
        worker.start()
        self.assertTrue(entered.wait(3))
        started = time.monotonic()
        runtime.assert_emergency_hold()
        self.assertLess(time.monotonic() - started, 0.5)
        proceed.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(runtime._emergency_hold)
        self.assertEqual(runtime.config.inference_profile, "SAFE_STOP")
        self.assertFalse(runtime.inspection_active)
        self.assertTrue(any("紧急停机" in item for item in errors))

    def test_resume_rejected_after_safe_stop(self):
        runtime = _runtime()
        runtime.assert_emergency_hold()
        with self.assertRaisesRegex(RuntimeError, "紧急停机"):
            runtime.start_inspection()

    def test_human_cannot_clear_hold_while_hot(self):
        runtime = _runtime()
        runtime.assert_emergency_hold()
        runtime._exec_authority = "human"
        runtime.current_snapshot = lambda: {"system": {"temperature_c": 91.0}, "mission": {"current_profile": "SAFE_STOP"}}
        ok, message = runtime.set_inference_profile("FULL")
        self.assertFalse(ok)
        self.assertIn("紧急停机", message)
        self.assertTrue(runtime._emergency_hold)
        self.assertEqual(runtime.config.inference_profile, "SAFE_STOP")

    def test_human_can_resume_when_cool(self):
        runtime = _runtime()
        runtime.assert_emergency_hold()
        runtime._exec_authority = "human"
        runtime.current_snapshot = lambda: {"system": {"temperature_c": 40.0}, "mission": {"current_profile": "SAFE_STOP"}}
        ok, message = runtime.set_inference_profile("SPARSE")
        self.assertTrue(ok, message)
        self.assertFalse(runtime._emergency_hold)
        self.assertEqual(runtime.config.inference_profile, "SPARSE")
        self.assertTrue(runtime.inspection_active)

    def test_agent_cannot_clear_hold_when_cool(self):
        runtime = _runtime()
        runtime.assert_emergency_hold()
        runtime._exec_authority = "agent"
        runtime.current_snapshot = lambda: {"system": {"temperature_c": 40.0}, "mission": {"current_profile": "SAFE_STOP"}}
        ok, message = runtime.set_inference_profile("FULL")
        self.assertFalse(ok)
        self.assertTrue(runtime._emergency_hold)

    def test_no_final_state_inversion(self):
        runtime = _runtime()
        runtime.config.inference_profile = "FULL"
        entered = threading.Event()
        proceed = threading.Event()

        def gated_drop():
            entered.set()
            proceed.wait(3)
            runtime.worker._inspector = None

        runtime.worker.drop_inspector = gated_drop
        runtime.config.validate_models = lambda: None

        def rebuild():
            try:
                runtime.rebuild_inspector(resume=True)
            except RuntimeError:
                pass

        thread = threading.Thread(target=rebuild)
        thread.start()
        self.assertTrue(entered.wait(3))
        runtime.assert_emergency_hold()
        proceed.set()
        thread.join(5)
        self.assertEqual(runtime.config.inference_profile, "SAFE_STOP")
        self.assertTrue(runtime._emergency_hold)
        self.assertFalse(runtime.inspection_active)
