"""Camera capture, frame sharing, and Qt image conversion."""

from pathlib import Path
import sys
import threading

import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel


class LatestFrame:
    """Thread-safe single-frame buffer that never builds a stale queue."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._sequence = 0

    def publish(self, frame):
        with self._lock:
            self._frame = frame.copy()
            self._sequence += 1

    def read(self):
        with self._lock:
            if self._frame is None:
                return self._sequence, None
            return self._sequence, self._frame.copy()


def frame_to_pixmap(frame, size):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(image).scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class CameraView(QLabel):
    def __init__(self, config, frame_store, parent=None):
        super().__init__(parent)
        self.config = config
        self.frame_store = frame_store
        self.capture = None
        self.error_message = ""
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(480, 360)
        self.setText("等待摄像头")
        self.setStyleSheet("background:#111827; color:#94a3b8; border-radius:8px;")

    def start(self):
        device_path = Path(f"/dev/video{self.config.camera_index}")
        if sys.platform.startswith("linux") and not device_path.exists():
            self.error_message = f"未找到摄像头设备 {device_path}"
            self.setText(self.error_message)
            return False
        self.capture = cv2.VideoCapture(self.config.camera_index, cv2.CAP_V4L2)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            self.error_message = f"无法打开摄像头设备 {device_path}，请检查权限"
            self.setText(self.error_message)
            return False
        self.error_message = ""
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
        self.capture.set(cv2.CAP_PROP_FPS, self.config.camera_fps)
        return True

    def capture_frame(self):
        if self.capture is None:
            return
        ok, frame = self.capture.read()
        if ok:
            self.frame_store.publish(frame)
            self.setPixmap(frame_to_pixmap(frame, self.size()))

    def stop(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None
