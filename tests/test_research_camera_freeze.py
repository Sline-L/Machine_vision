import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gp.research_inject import (
    allow_restart_camera,
    clear_research_camera_freeze,
    freeze_camera_requested,
    research_inject_enabled,
)


class ResearchCameraFreezeTests(unittest.TestCase):
    def test_disabled_without_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GEARPRO_RESEARCH_INJECT", None)
            self.assertFalse(research_inject_enabled())
            self.assertFalse(freeze_camera_requested())

    def test_freeze_file_ignored_when_inject_env_not_one(self):
        path = Path(tempfile.mkdtemp()) / "freeze"
        path.write_text("x", encoding="utf-8")
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ["GEARPRO_INJECT_FREEZE_CAMERA"] = str(path)
            self.assertFalse(research_inject_enabled())
            self.assertFalse(freeze_camera_requested())
        with mock.patch.dict(
            os.environ,
            {"GEARPRO_RESEARCH_INJECT": "0", "GEARPRO_INJECT_FREEZE_CAMERA": str(path)},
        ):
            self.assertFalse(freeze_camera_requested())

    def test_freeze_file_only_when_enabled(self):
        path = Path(tempfile.mkdtemp()) / "freeze"
        with mock.patch.dict(
            os.environ,
            {"GEARPRO_RESEARCH_INJECT": "1", "GEARPRO_INJECT_FREEZE_CAMERA": str(path)},
        ):
            self.assertFalse(freeze_camera_requested())
            path.write_text("x", encoding="utf-8")
            self.assertTrue(freeze_camera_requested())
            clear_research_camera_freeze()
            self.assertFalse(path.exists())
            self.assertFalse(freeze_camera_requested())

    def test_restart_camera_not_widened_for_file_video(self):
        self.assertTrue(allow_restart_camera("camera"))
        self.assertTrue(allow_restart_camera("replay"))
        self.assertFalse(allow_restart_camera("video"))
