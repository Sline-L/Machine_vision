"""GearPro application entry point."""

import os
import sys

from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtWidgets import QApplication


def configure_qt_platform():
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    else:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def main():
    configure_qt_platform()
    from gearpro_config import AppConfig
    from gearpro_ui import APP_STYLE, MainWindow

    # Importing gearpro_ui imports cv2, whose wheel rewrites the Qt plugin path
    # to cv2/qt/plugins. Restore PyQt5's plugin directory before QApplication.
    configure_qt_platform()
    app = QApplication(sys.argv)
    app.setApplicationName("GearPro")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow(AppConfig.from_environment())
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
