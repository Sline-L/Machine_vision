# 设置Qt应用程序属性，避免线程问题
import os
import sys
from PyQt5.QtWidgets import QApplication

import gp_mainwindow

def main():
    
   
    os.environ["QT_QPA_PLATFORM"] = "xcb"  # 使用X11而不是Wayland
    
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