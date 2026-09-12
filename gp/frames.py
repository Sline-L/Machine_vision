"""Thread-safe latest-frame buffer with capture timing."""

from dataclasses import dataclass
import threading
import time
from typing import Optional


@dataclass
class FramePacket:
    sequence: int
    frame: Optional[object]
    age_ms: Optional[float]
    published_at: Optional[float]


class LatestFrame:
    """Keep only the newest frame; never queue stale images."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._sequence = 0
        self._published_at = None

    def publish(self, frame):
        with self._lock:
            self._frame = frame.copy()
            self._sequence += 1
            self._published_at = time.monotonic()

    def read(self):
        with self._lock:
            if self._frame is None:
                return FramePacket(self._sequence, None, None, self._published_at)
            age_ms = None
            if self._published_at is not None:
                age_ms = (time.monotonic() - self._published_at) * 1000.0
            return FramePacket(self._sequence, self._frame.copy(), age_ms, self._published_at)

    def meta(self):
        packet = self.read()
        return packet.sequence, packet.age_ms

    def clear(self):
        with self._lock:
            self._frame = None
            self._sequence += 1
            self._published_at = None
