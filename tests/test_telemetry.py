import time
import unittest

from gp.config import AppConfig
from gp.frames import LatestFrame
from gp.serial_io import SerialOutput
from gp.telemetry import build_snapshot, camera_health, locator_backend
from gp.profiles import apply_to_config
from gp.types import InspectionResult


class _Frame:
    def copy(self):
        return self


class FrameBufferTests(unittest.TestCase):
    def test_sequence_and_age(self):
        store = LatestFrame()
        empty = store.read()
        self.assertEqual(empty.sequence, 0)
        self.assertIsNone(empty.frame)
        store.publish(_Frame())
        time.sleep(0.02)
        packet = store.read()
        self.assertEqual(packet.sequence, 1)
        self.assertIsNotNone(packet.frame)
        self.assertGreater(packet.age_ms, 10)


class SnapshotTests(unittest.TestCase):
    def test_locator_backend_from_suffix(self):
        self.assertEqual(locator_backend("model/model1.pt"), "pt")
        self.assertEqual(locator_backend("model1.engine"), "engine")

    def test_stale_camera_health_is_zero(self):
        self.assertEqual(camera_health(True, 1500, 0), 0.0)
        self.assertEqual(camera_health(False, 10, 0), 0.0)

    def test_snapshot_has_v2_specialists(self):
        config = AppConfig()
        store = LatestFrame()
        serial = SerialOutput("/dev/null", 9600)
        serial.last_send_ok = False
        serial.consecutive_failures = 2
        serial.last_error = "offline"
        result = InspectionResult(
            annotated_frame=None,
            locator_latency_ms=18.0,
            classifier1_latency_ms=7.0,
            classifier2_latency_ms=6.0,
            detector_latency_ms=40.0,
            fusion_latency_ms=0.2,
            scratch_latency_ms=53.2,
            missing_hole_classifier1_latency_ms=8.0,
            missing_hole_classifier2_latency_ms=7.0,
            missing_hole_detector_latency_ms=45.0,
            missing_hole_fusion_latency_ms=0.3,
            missing_hole_latency_ms=60.3,
        )
        snapshot = build_snapshot(
            config,
            store,
            camera_opened=True,
            camera_device="/dev/video0",
            read_failures=0,
            actual_fps=12.0,
            serial=serial,
            last_result=result,
            inspection_active=True,
        )
        self.assertEqual(snapshot["schema_version"], "system-snapshot.v2")
        for key in ("system", "camera", "locator", "specialists", "inference", "serial", "mission"):
            self.assertIn(key, snapshot)
        self.assertEqual(snapshot["locator"]["backend"], "pt")
        self.assertEqual(snapshot["specialists"]["scratch_v5"]["profile"], "FULL")
        self.assertEqual(snapshot["specialists"]["missing_hole_v1"]["total_latency_ms"], 60.3)
        self.assertEqual(snapshot["mission"]["current_profile"], "FULL")
        self.assertEqual(snapshot["mission"]["utility"], 0.8)
        self.assertEqual(snapshot["serial"]["consecutive_failures"], 2)
        missing = snapshot["specialists"]["missing_hole_v1"]
        self.assertIsNone(missing["error_count"])
        self.assertEqual(missing["error_state"], "unknown")
        self.assertIsNone(missing["loaded"])
        self.assertIn("inspection_count", snapshot["mission"])

    def test_v1_snapshot_remains_available(self):
        snapshot = build_snapshot(
            AppConfig(),
            LatestFrame(),
            camera_opened=False,
            camera_device="/dev/video0",
            read_failures=0,
            actual_fps=0.0,
            serial=None,
            schema_version="system-snapshot.v1",
        )
        self.assertEqual(snapshot["schema_version"], "system-snapshot.v1")
        self.assertIn("scratch_v5", snapshot)
        self.assertNotIn("specialists", snapshot)

    def test_snapshot_tracks_named_profile(self):
        config = AppConfig()
        apply_to_config(config, "SPARSE")
        store = LatestFrame()
        snapshot = build_snapshot(
            config,
            store,
            camera_opened=True,
            camera_device="/dev/video0",
            read_failures=0,
            actual_fps=12.0,
            serial=None,
            last_result=None,
            inspection_active=False,
        )
        self.assertEqual(snapshot["mission"]["current_profile"], "SPARSE")
        self.assertEqual(snapshot["mission"]["utility"], 0.45)

    def test_missing_hole_load_failure_does_not_copy_scratch_errors(self):
        snapshot = build_snapshot(
            AppConfig(),
            LatestFrame(),
            camera_opened=True,
            camera_device="/dev/video0",
            read_failures=0,
            actual_fps=12.0,
            serial=None,
            last_result=None,
            inspection_active=False,
            scratch_errors=3,
            specialist_status={"scratch_v5": "loaded", "missing_hole_v1": "failed", "locator": "loaded"},
            last_error_source="missing_hole_v1",
            inspect_count=4,
        )
        scratch = snapshot["specialists"]["scratch_v5"]
        missing = snapshot["specialists"]["missing_hole_v1"]
        self.assertEqual(scratch["loaded"], True)
        self.assertEqual(missing["loaded"], False)
        self.assertEqual(missing["error_state"], "load_failed")
        self.assertEqual(missing["error_count"], 1)
        self.assertEqual(scratch["error_count"], 3)
        self.assertNotEqual(scratch["error_count"], missing["error_count"])
        self.assertEqual(snapshot["mission"]["inspection_count"], 4)


class SerialStatsTests(unittest.TestCase):
    def test_failures_accumulate_until_success(self):
        output = SerialOutput("COM_INVALID", 9600)
        ok, _message = output.send("01")
        self.assertFalse(ok)
        self.assertEqual(output.consecutive_failures, 1)
        self.assertFalse(output.last_send_ok)


if __name__ == "__main__":
    unittest.main()
