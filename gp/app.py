"""GearPro application entry point."""

import os
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


def main():
    configure_qt_platform()
    from .config import AppConfig
    from .ui import APP_STYLE, MainWindow

    # Importing gp.ui imports cv2, whose wheel rewrites the Qt plugin path
    # to cv2/qt/plugins. Restore PyQt5's plugin directory before QApplication.
    configure_qt_platform()
    app = QApplication(sys.argv)
    app.setApplicationName("GearPro")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow(AppConfig.from_environment())
    window.show()
    return app.exec_()
