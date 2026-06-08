import time
from PyQt5.QtWidgets import (QMainWindow, QLabel, QVBoxLayout, 
                             QWidget, QHBoxLayout)
from PyQt5.QtCore import QTimer, Qt


import gp_cameradisplaywidget
import gp_detectiondisplaywidget
import gp_globals


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO实时检测系统")
        self.setGeometry(100, 100, 1280, 600)
        
        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 标题标签
        title_label = QLabel("YOLOv8 实时目标检测系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #ffffff;
            padding: 15px;
            background-color: #2c3e50;
            border-radius: 8px;
            margin-bottom: 10px;
        """)
        main_layout.addWidget(title_label)
        
        # 创建显示区域（左右布局）
        display_layout = QHBoxLayout()
        
        # 左侧摄像头显示区域（只显示原始画面）
        self.camera1 = gp_cameradisplaywidget.CameraDisplayWidget(2)
        display_layout.addWidget(self.camera1)
        
        # 右侧检测结果显示区域
        self.detection_display = gp_detectiondisplaywidget.DetectionDisplayWidget()
        display_layout.addWidget(self.detection_display)
        
        main_layout.addLayout(display_layout)
        
        # 状态标签
        self.status_label = QLabel("准备启动摄像头...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #666666; 
            padding: 10px;
            background-color: #ecf0f1;
            border-radius: 5px;
            margin-top: 5px;
        """)
        main_layout.addWidget(self.status_label)
        
        # 设置定时器用于更新画面
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_cameras)
        self.timer.start(30)  # 约30fps
        
        # 启动摄像头
        self.start_cameras()
    
    def start_cameras(self):
        """启动摄像头"""
        cam1_started = self.camera1.start_camera()
        if cam1_started:
            self.status_label.setText("✅ 摄像头已启动，点击右侧'开始检测'按钮进行YOLO检测")
            self.status_label.setStyleSheet(self.status_label.styleSheet().replace("#666666", "#27ae60"))
            self.timer.start()
        else:
            self.status_label.setText("❌ 无法启动摄像头，请检查连接")
            self.status_label.setStyleSheet(self.status_label.styleSheet().replace("#666666", "#e74c3c"))
    
    def update_cameras(self):
        """更新摄像头的画面"""
        self.camera1.update_frame()
    
    def closeEvent(self, event):
        """窗口关闭时释放资源"""
      
        gp_globals.running = False
        self.timer.stop()
        self.camera1.stop_camera()
        self.detection_display.stop_detection_thread()
        time.sleep(0.5)  # 等待线程结束
        event.accept()
        