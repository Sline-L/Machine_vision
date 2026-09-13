"""Headless OpenCV camera capture for the Web runtime."""

from collections import deque
from pathlib import Path
import sys
import threading
import time

import cv2


class CameraCapture:
    def __init__(self, config, frame_store):
        self.config = config
        self.frame_store = frame_store
        self.capture = None
        self.error_message = ""
        self.read_failures = 0
        self._ok_stamps = deque()
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._stats_lock = threading.Lock()

    @property
    def device_path(self):
        return f"/dev/video{self.config.camera_index}"

    @property
    def opened(self):
        with self._lock:
            return self.capture is not None and self.capture.isOpened()

    @property
    def actual_fps(self):
        now = time.monotonic()
        with self._stats_lock:
            while self._ok_stamps and now - self._ok_stamps[0] > 1.0:
                self._ok_stamps.popleft()
            return float(len(self._ok_stamps))

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_event.clear()
        if not self._open():
            return False
        self._thread = threading.Thread(target=self._capture_loop, name="gearpro-camera", daemon=True)
        self._thread.start()
        return True

    def _open(self):
        device_path = Path(self.device_path)
        if sys.platform.startswith("linux") and not device_path.exists():
            self.error_message = f"未找到摄像头设备 {device_path}"
            return False
        backends = (cv2.CAP_V4L2,) if sys.platform.startswith("linux") else (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
        capture = None
        for backend in backends:
            candidate = cv2.VideoCapture(self.config.camera_index, backend)
            if candidate.isOpened():
                capture = candidate
                break
            candidate.release()
        if capture is None:
            self.error_message = f"无法打开摄像头设备 {device_path}，请检查权限"
            return False
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
        capture.set(cv2.CAP_PROP_FPS, self.config.camera_fps)
        with self._lock:
            self.capture = capture
        self.error_message = ""
        self.read_failures = 0
        with self._stats_lock:
            self._ok_stamps.clear()
        return True

    def _capture_loop(self):
        frame_period = 1.0 / max(1, self.config.camera_fps)
        while not self._stop_event.is_set():
            started = time.monotonic()
            with self._lock:
                capture = self.capture
            if capture is None:
                return
            ok, frame = capture.read()
            if ok:
                self.read_failures = 0
                with self._stats_lock:
                    self._ok_stamps.append(time.monotonic())
                self.frame_store.publish(frame)
            else:
                self.read_failures += 1
                self.error_message = "摄像头读取失败"
            remaining = frame_period - (time.monotonic() - started)
            if remaining > 0:
                self._stop_event.wait(remaining)

    def stop(self):
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        with self._lock:
            capture = self.capture
            self.capture = None
        if capture is not None:
            capture.release()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None

    def restart(self):
        self.stop()
        return self.start()
