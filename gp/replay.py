"""Disk image replay as a CameraCapture-compatible frame producer."""

from collections import deque
from pathlib import Path
import threading
import time

import cv2


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def list_replay_images(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"找不到 replay 目录：{directory}")
    images = sorted(
        path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise FileNotFoundError(f"replay 目录没有图片：{directory}")
    return images


class ReplayCapture:
    """Publish dataset images into LatestFrame at camera_fps. Not a live sensor."""

    def __init__(self, config, frame_store, on_complete=None):
        self.config = config
        self.frame_store = frame_store
        self.on_complete = on_complete
        self.error_message = ""
        self.read_failures = 0
        self._ok_stamps = deque()
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._opened = False
        self._images = []

    @property
    def device_path(self):
        directory = getattr(self.config, "replay_dir", None)
        return f"replay:{directory}" if directory is not None else "replay"

    @property
    def opened(self):
        with self._lock:
            return self._opened

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
        try:
            self._images = list_replay_images(self.config.replay_dir)
        except FileNotFoundError as exc:
            self.error_message = str(exc)
            with self._lock:
                self._opened = False
            return False
        self._stop_event.clear()
        with self._lock:
            self._opened = True
        self.error_message = ""
        self.read_failures = 0
        with self._stats_lock:
            self._ok_stamps.clear()
        self._thread = threading.Thread(target=self._loop, name="gearpro-replay", daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        frame_period = 1.0 / max(1, int(self.config.camera_fps))
        index = 0
        loop = bool(getattr(self.config, "replay_loop", True))
        while not self._stop_event.is_set():
            started = time.monotonic()
            path = self._images[index]
            frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if frame is None:
                self.read_failures += 1
                self.error_message = f"无法读取 replay 图片：{path.name}"
            else:
                self.read_failures = 0
                with self._stats_lock:
                    self._ok_stamps.append(time.monotonic())
                self.frame_store.publish(frame)
            index += 1
            if index >= len(self._images):
                if not loop:
                    callback = self.on_complete
                    self._stop_event.set()
                    with self._lock:
                        self._opened = True
                    if callback is not None:
                        callback()
                    return
                index = 0
            remaining = frame_period - (time.monotonic() - started)
            if remaining > 0:
                self._stop_event.wait(remaining)

    def stop(self):
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        with self._lock:
            self._opened = False
        self._thread = None

    def restart(self):
        self.stop()
        return self.start()
