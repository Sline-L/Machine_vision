"""Background inspection thread."""

import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal

from .models import TwoStageInspector


class InspectionThread(QThread):
    result_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, config, frame_store, parent=None):
        super().__init__(parent)
        self.config = config
        self.frame_store = frame_store
        self._stop_event = threading.Event()

    def run(self):
        try:
            self.status_changed.emit("正在加载两阶段模型…")
            inspector = TwoStageInspector(self.config)
            if self.config.video_path is not None:
                self._inspect_video(inspector)
                return
            self.status_changed.emit("检测运行中")
            last_sequence = -1
            while not self._stop_event.is_set():
                sequence, frame = self.frame_store.read()
                if frame is not None and sequence != last_sequence:
                    last_sequence = sequence
                    self.result_ready.emit(inspector.inspect(frame))
                self._stop_event.wait(self.config.inference_interval)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if self._stop_event.is_set():
                self.status_changed.emit("检测已停止")

    def _inspect_video(self, inspector):
        import cv2

        capture = cv2.VideoCapture(str(self.config.video_path))
        if not capture.isOpened():
            raise RuntimeError(f"无法打开测试视频：{self.config.video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_period = 1.0 / fps if fps and fps > 0 else self.config.inference_interval
        self.status_changed.emit(f"视频测试运行中：{self.config.video_path.name}")
        try:
            while not self._stop_event.is_set():
                started = time.monotonic()
                ok, frame = capture.read()
                if not ok:
                    self.status_changed.emit("视频识别完成")
                    return
                self.result_ready.emit(inspector.inspect(frame))
                remaining = frame_period - (time.monotonic() - started)
                if remaining > 0:
                    self._stop_event.wait(remaining)
        finally:
            capture.release()

    def request_stop(self):
        self._stop_event.set()
