import cv2
from PyQt5.QtWidgets import QLabel                             
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt


import gp_globals


class CameraDisplayWidget(QLabel):
    """用于显示摄像头画面的自定义控件（只显示原始画面）"""
    def __init__(self, camera_index=2, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.cap = None
        self.setMinimumSize(640, 480)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 2px solid #cccccc; background-color: #f0f0f0;")
        
    def start_camera(self):
        """启动摄像头"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.setText("摄像头打开失败")
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            return True
        except Exception as e:
            print(f"摄像头启动错误: {e}")
            self.setText(f"错误: {str(e)}")
            return False
    
    def update_frame(self):
        """更新当前帧（只显示原始画面）"""
        if self.cap and self.cap.isOpened():
            ret, new_frame = self.cap.read()
            if ret:
                # 更新全局帧用于YOLO处理
                with gp_globals.frame_lock:
                    gp_globals.frame = new_frame.copy()
                
                # 只显示原始画面，不绘制检测框
                display_frame = new_frame.copy()
                
                # 转换为RGB并显示
                frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.setPixmap(QPixmap.fromImage(qt_image).scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def stop_camera(self):
        """停止摄像头"""
        if self.cap:
            self.cap.release()
            self.cap = None
