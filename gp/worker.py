"""Background inspection thread."""

import threading

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

    def request_stop(self):
        self._stop_event.set()
