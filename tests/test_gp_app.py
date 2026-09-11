import os
import unittest
from unittest.mock import patch

from gp.app import build_parser, configure_qt_platform


class QtPlatformTests(unittest.TestCase):
    def test_wayland_session_uses_wayland_plugin(self):
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
            configure_qt_platform()
            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "wayland")
            self.assertEqual(os.environ["QT_QPA_PLATFORMTHEME"], "none")

    def test_headless_session_uses_offscreen_plugin(self):
        with patch.dict(os.environ, {}, clear=True):
            configure_qt_platform()
            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "offscreen")

    def test_qt5_isolates_incompatible_kde6_font_settings(self):
        environment = {"KDE_SESSION_VERSION": "6", "XDG_CURRENT_DESKTOP": "KDE"}
        with patch.dict(os.environ, environment, clear=True):
            configure_qt_platform()
            self.assertEqual(os.environ["XDG_CURRENT_DESKTOP"], "generic")


class CommandLineTests(unittest.TestCase):
    def test_video_argument_accepts_path(self):
        args = build_parser().parse_args(["--video", "fixtures/gears.mp4"])
        self.assertEqual(str(args.video), "fixtures/gears.mp4")


if __name__ == "__main__":
    unittest.main()
