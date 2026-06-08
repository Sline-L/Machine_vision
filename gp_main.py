# 设置Qt应用程序属性，避免线程问题
import os
import sys
from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtWidgets import QApplication


def configure_qt_platform():
    """确保 PyQt5 使用自己的 Qt 插件，避免被 cv2 的插件路径覆盖。"""
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    else:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


configure_qt_platform()

import gp_mainwindow

def main():
    configure_qt_platform()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置全局样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f6fa;
        }
    """)
    
    window = gp_mainwindow.MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
