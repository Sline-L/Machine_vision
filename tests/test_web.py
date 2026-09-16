from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
import numpy as np

from gp.auth import SessionManager
from gp.config import AppConfig
from gp.runtime import GearProRuntime
from gp.types import GearObservation, InspectionResult
from gp.web import create_app


class FakeRuntime:
    def __init__(self, config):
        self.config = config
        self.active = False
        self.resets = 0

    def state(self, control=None, api_version="api.v2"):
        return {"version": api_version, "control": control or {}, "inspection": {"active": self.active}}

    def start_inspection(self):
        self.active = True

    def stop_inspection(self):
        self.active = False

    def human_action(self, name, params=None):
        params = params or {}
        if name == "resume_inspection":
            self.start_inspection()
        elif name == "pause_inspection":
            self.stop_inspection()
        elif name == "use_camera":
            self.use_camera()
        elif name == "use_video":
            self.use_video(params.get("path"), params.get("managed"))
        elif name == "apply_settings":
            self.update_settings(params)
        elif name == "reset_stats":
            self.reset_stats()
        else:
            return {
                "accepted": False,
                "executed": False,
                "error": f"未知动作：{name}",
            }
        return {
            "accepted": True,
            "executed": True,
            "verified": False,
            "recovery_success": False,
            "config_verified": True,
            "verify_level": "config",
            "error": None,
        }

    def use_camera(self):
        pass

    def use_video(self, path, managed=False):
        del path, managed

    def update_settings(self, values):
        self.config.update(values)

    def reset_stats(self):
        self.resets += 1

    def jpeg(self, view):
        del view
        return b"jpeg"


class SessionTests(unittest.TestCase):
    def test_password_and_single_operator_lease(self):
        sessions = SessionManager("secret", control_ttl=0.02)
        with self.assertRaises(ValueError):
            sessions.login("wrong")
        one = sessions.login("secret", "一号")
        two = sessions.login("secret", "二号")
        sessions.acquire(one)
        with self.assertRaises(PermissionError):
            sessions.acquire(two)
        time.sleep(0.03)
        sessions.acquire(two)
        self.assertTrue(sessions.owns_control(two))


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = AppConfig()
        self.runtime = FakeRuntime(self.config)
        self.sessions = SessionManager("secret")
        self.app = create_app(self.config, self.runtime, self.sessions, manage_lifespan=False)
        transport = httpx.ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def login(self, client=None, label="测试终端"):
        client = client or self.client
        response = await client.post("/api/v1/session/login", json={"password": "secret", "label": label})
        self.assertEqual(response.status_code, 200)

    async def login_v2(self, client=None, label="测试终端"):
        client = client or self.client
        response = await client.post("/api/v2/session/login", json={"password": "secret", "label": label})
        self.assertEqual(response.status_code, 200)

    async def test_state_requires_login(self):
        self.assertEqual((await self.client.get("/api/v1/state")).status_code, 401)
        await self.login()
        self.assertEqual((await self.client.get("/api/v1/state")).status_code, 200)

    async def test_v1_and_v2_return_matching_versions(self):
        await self.login_v2()
        self.assertEqual((await self.client.get("/api/v1/state")).json()["version"], "api.v1")
        self.assertEqual((await self.client.get("/api/v2/state")).json()["version"], "api.v2")

    async def test_mutation_requires_control_and_lock_is_exclusive(self):
        await self.login()
        self.assertEqual((await self.client.post("/api/v1/inspection/start")).status_code, 423)
        self.assertEqual((await self.client.post("/api/v1/control/acquire")).status_code, 200)
        self.assertEqual((await self.client.post("/api/v1/inspection/start")).status_code, 200)
        self.assertTrue(self.runtime.active)
        other = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        try:
            await self.login(other, "旁观终端")
            self.assertEqual((await other.post("/api/v1/control/acquire")).status_code, 423)
        finally:
            await other.aclose()

    async def test_setting_validation_rejects_unknown_key(self):
        await self.login()
        await self.client.post("/api/v1/control/acquire")
        response = await self.client.put("/api/v1/settings", json={"unknown": 1})
        self.assertEqual(response.status_code, 400)


class PersistenceTests(unittest.TestCase):
    def test_non_secret_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config = AppConfig()
            config.update({"camera_index": 7, "defect_threshold": 0.456789})
            config.persist(path)
            restored = AppConfig()
            loaded = restored.load_persisted(path)
            self.assertEqual(restored.camera_index, 7)
            self.assertAlmostEqual(restored.scratch_threshold, 0.456789)
            self.assertIn("scratch_threshold", loaded)
            self.assertNotIn("password", path.read_text(encoding="utf-8"))

    def test_conflicting_legacy_and_v2_thresholds_are_rejected(self):
        config = AppConfig()
        with self.assertRaisesRegex(ValueError, "冲突"):
            config.update({"defect_threshold": 0.4, "scratch_threshold": 0.5})


class RuntimeSafetyTests(unittest.TestCase):
    def test_result_serializers_keep_v1_shape_and_expose_v2_specialists(self):
        observation = GearObservation(
            (1, 2, 30, 40), 0.9, 0.2,
            scratch_threshold=0.3,
            scratch_reject=False,
            missing_hole_probability=0.8,
            missing_hole_threshold=0.4,
            missing_hole_reject=True,
        )
        result = InspectionResult(
            None,
            [observation],
            model_version="scratch_v5",
            missing_hole_model_version="missing_hole_v1",
        )
        v1 = GearProRuntime._serialize_result_v1(result)
        v2 = GearProRuntime._serialize_result_v2(result)
        self.assertNotIn("missing_hole_probability", v1["observations"][0])
        self.assertEqual(v2["reject_reasons"], ["missing_hole"])
        self.assertTrue(v2["observations"][0]["specialists"]["missing_hole"]["reject"])

    def test_jpeg_is_encoded_once_for_the_same_frame(self):
        runtime = GearProRuntime(AppConfig())
        runtime.raw_frames.publish(np.zeros((8, 8, 3), dtype=np.uint8))
        encoded = np.array([1, 2, 3], dtype=np.uint8)
        with patch("gp.runtime.cv2.imencode", return_value=(True, encoded)) as imencode:
            self.assertEqual(runtime.jpeg("raw"), b"\x01\x02\x03")
            self.assertEqual(runtime.jpeg("raw"), b"\x01\x02\x03")
        self.assertEqual(imencode.call_count, 1)

    def test_worker_error_never_counts_or_sends_serial(self):
        runtime = GearProRuntime(AppConfig())
        with patch.object(runtime.serial, "send_verdict") as send:
            runtime._on_error("CUDA OOM")
        self.assertEqual(runtime.stats.total, 0)
        self.assertEqual(runtime.error, "CUDA OOM")
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
