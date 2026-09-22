"""Lazy, thread-safe serial output for inspection verdicts."""

import threading


class SerialOutput:
    GOOD_CODE = "01"
    DEFECTIVE_CODE = "02"

    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._lock = threading.Lock()
        self.last_send_ok = None
        self.consecutive_failures = 0
        self.last_error = None

    @property
    def is_open(self):
        return self._serial is not None and self._serial.is_open

    def send_verdict(self, defective):
        return self.send(self.DEFECTIVE_CODE if defective else self.GOOD_CODE)

    def send(self, text):
        with self._lock:
            try:
                if self._serial is None or not self._serial.is_open:
                    import serial
                    self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
                self._serial.write(text.encode("ascii"))
                self.last_send_ok = True
                self.consecutive_failures = 0
                self.last_error = None
                return True, f"串口已发送 {text}"
            except Exception as exc:
                self.last_send_ok = False
                self.consecutive_failures += 1
                self.last_error = str(exc)
                return False, f"串口发送失败：{exc}"

    def reconfigure(self, port, baudrate):
        self.close()
        self.port = port
        self.baudrate = baudrate

    def close(self):
        with self._lock:
            if self._serial is not None and self._serial.is_open:
                self._serial.close()
            self._serial = None
