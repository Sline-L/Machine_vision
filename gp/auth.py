"""Small in-memory session and single-operator lease manager."""

import hmac
import secrets
import threading
import time


class SessionManager:
    COOKIE_NAME = "gearpro_session"

    def __init__(self, password, session_ttl=8 * 60 * 60, control_ttl=30.0):
        self.password = password or ""
        self.session_ttl = float(session_ttl)
        self.control_ttl = float(control_ttl)
        self._sessions = {}
        self._control_owner = None
        self._control_deadline = 0.0
        self._lock = threading.RLock()

    @property
    def password_required(self):
        return bool(self.password)

    def login(self, password, label="操作终端"):
        if not hmac.compare_digest(str(password or ""), self.password):
            raise ValueError("密码错误")
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._sessions[token] = {
                "label": str(label or "操作终端")[:64],
                "expires": now + self.session_ttl,
            }
        return token

    def logout(self, token):
        with self._lock:
            self._sessions.pop(token, None)
            if self._control_owner == token:
                self._control_owner = None
                self._control_deadline = 0.0

    def validate(self, token):
        if not token:
            return False
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            session = self._sessions.get(token)
            if session is None or session["expires"] <= now:
                self._sessions.pop(token, None)
                return False
            session["expires"] = now + self.session_ttl
            return True

    def acquire(self, token):
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            if token not in self._sessions:
                raise PermissionError("会话已失效")
            if self._control_owner not in (None, token):
                raise PermissionError("另一终端正在控制设备")
            self._control_owner = token
            self._control_deadline = now + self.control_ttl
            return self.control_state(token)

    def heartbeat(self, token):
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            if self._control_owner != token:
                return False
            self._control_deadline = now + self.control_ttl
            return True

    def release(self, token):
        with self._lock:
            if self._control_owner == token:
                self._control_owner = None
                self._control_deadline = 0.0

    def owns_control(self, token):
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            return self._control_owner == token

    def control_state(self, viewer=None):
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            session = self._sessions.get(self._control_owner)
            return {
                "occupied": self._control_owner is not None,
                "is_owner": self._control_owner == viewer,
                "owner_label": None if session is None else session["label"],
                "expires_in": max(0.0, self._control_deadline - now) if session else 0.0,
            }

    def _expire(self, now):
        expired = [token for token, item in self._sessions.items() if item["expires"] <= now]
        for token in expired:
            self._sessions.pop(token, None)
        if self._control_owner not in self._sessions or self._control_deadline <= now:
            self._control_owner = None
            self._control_deadline = 0.0
