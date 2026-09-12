"""GearPro application entry point."""

import argparse
import os
from pathlib import Path
import sys

from PyQt5.QtCore import QLibraryInfo, QT_VERSION_STR
from PyQt5.QtWidgets import QApplication


def configure_qt_platform():
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    # The application uses its own Fusion stylesheet. Avoid parsing KDE's Qt 6
    # font serialization with the bundled Qt 5 runtime.
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "none")
    if os.environ.get("KDE_SESSION_VERSION") == "6" and QT_VERSION_STR.startswith("5."):
        os.environ["XDG_CURRENT_DESKTOP"] = "generic"
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    elif os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
    else:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def build_parser():
    parser = argparse.ArgumentParser(description="GearPro 齿轮视觉检测系统")
    parser.add_argument("--video", type=Path, help="使用视频文件进入测试模式")
    parser.add_argument(
        "--control-port",
        type=int,
        default=int(os.getenv("GEARPRO_CONTROL_PORT", "8787")),
        help="本机 Control API 端口，0 关闭",
    )
    parser.add_argument("--no-control", action="store_true", help="不启动 Control API")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_qt_platform()
    from .config import AppConfig
    from .ui import APP_STYLE, MainWindow

    config = AppConfig.from_environment()
    config.control_host = os.getenv("GEARPRO_CONTROL_HOST", "127.0.0.1")
    config.control_port = 0 if args.no_control else args.control_port
    if args.video is not None:
        video_path = args.video.expanduser().resolve()
        if not video_path.is_file():
            parser.error(f"找不到视频文件：{video_path}")
        config.video_path = video_path
        config.mode = "视频测试模式"
        config.serial_enabled = False

    # Importing gp.ui imports cv2, whose wheel rewrites the Qt plugin path
    # to cv2/qt/plugins. Restore PyQt5's plugin directory before QApplication.
    configure_qt_platform()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("GearPro")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow(config)
    window.show()
    return app.exec_()
