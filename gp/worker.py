"""Persistent, headless inspection worker."""

import threading
import time

from .models import TwoStageInspector


class InspectionWorker:
    def __init__(self, config, frame_store, on_result, on_status, on_error, on_video_complete):
        self.config = config
        self.frame_store = frame_store
        self.on_result = on_result
        self.on_status = on_status
        self.on_error = on_error
        self.on_video_complete = on_video_complete
        self._stop_event = threading.Event()
        self._active_event = threading.Event()
        self._interrupt_event = threading.Event()
        self._thread = None
        self._inspector = None
        self.inspect_count = 0
        self._inspect_lock = threading.Lock()

    def bump_inspect(self):
        with self._inspect_lock:
            self.inspect_count += 1
            return self.inspect_count

    @property
    def active(self):
        return self._active_event.is_set()

    @property
    def model_loaded(self):
        return self._inspector is not None

    def start_service(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run, name="gearpro-inspection", daemon=True)
        self._thread.start()

    def start_inspection(self):
        self._interrupt_event.clear()
        self._active_event.set()

    def pause(self):
        self._active_event.clear()
        self._interrupt_event.set()

    def run(self):
        try:
            while not self._stop_event.is_set():
                if not self._active_event.wait(0.2):
                    continue
                try:
                    if self._inspector is None:
                        self.on_status("正在加载两阶段模型…")
                        self._inspector = TwoStageInspector(self.config)
                    if self.config.video_path is not None:
                        self._inspect_video(self._inspector)
                    else:
                        self._inspect_camera(self._inspector)
                except Exception as exc:
                    self._active_event.clear()
                    self.on_error(f"{type(exc).__name__}: {exc}")
        finally:
            self.on_status("检测服务已停止")

    def _inspect_camera(self, inspector):
        self.on_status("检测运行中")
        last_sequence = -1
        while self.active and not self._stop_event.is_set() and self.config.video_path is None:
            packet = self.frame_store.read()
            if packet.frame is not None and packet.sequence != last_sequence:
                last_sequence = packet.sequence
                self.bump_inspect()
                self.on_result(inspector.inspect(packet.frame))
            self._interrupt_event.wait(self.config.inference_interval)

    def _inspect_video(self, inspector):
        import cv2

        capture = cv2.VideoCapture(str(self.config.video_path))
        if not capture.isOpened():
            raise RuntimeError(f"无法打开测试视频：{self.config.video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_period = 1.0 / fps if fps and fps > 0 else self.config.inference_interval
        video_path = self.config.video_path
        self.on_status(f"视频测试运行中：{video_path.name}")
        try:
            while self.active and not self._stop_event.is_set() and self.config.video_path == video_path:
                started = time.monotonic()
                ok, frame = capture.read()
                if not ok:
                    self._active_event.clear()
                    self.on_status("视频识别完成")
                    self.on_video_complete(video_path)
                    return
                self.frame_store.publish(frame)
                self.bump_inspect()
                self.on_result(inspector.inspect(frame))
                remaining = frame_period - (time.monotonic() - started)
                if remaining > 0:
                    self._interrupt_event.wait(remaining)
        finally:
            capture.release()

    def drop_inspector(self):
        self.pause()
        time.sleep(max(0.12, float(getattr(self.config, "inference_interval", 0.1)) + 0.05))
        self._inspector = None

    def stop_service(self):
        self._active_event.clear()
        self._stop_event.set()
        self._interrupt_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)
        self._thread = None
        self._inspector = None
