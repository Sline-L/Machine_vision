"""Localhost Control API for EdgeMedic. No Qt; talks to GearProRuntime."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from urllib.parse import urlparse

from .actions import SPECS, ActionError, accept, parse_request, verify


class ControlService:
    def __init__(self, runtime):
        self.runtime = runtime

    def snapshot(self):
        return self.runtime.current_snapshot()

    def extras(self):
        return self.runtime.control_extras()

    def execute(self, name, params):
        return self.runtime.execute_action(name, params)

    def rollback(self, name, token):
        return self.runtime.rollback_action(name, token)

    def run_action(self, body):
        started = time.monotonic()
        request = parse_request(body)
        name = request["name"]
        params = request["params"]
        meta = SPECS[name]
        before = self.snapshot()
        extras = self.extras()
        allowed, reason = accept(name, params, before, extras)
        if not allowed:
            return _response(request, False, False, False, reason, before, before, started)
        if name == "get_state":
            after = before
            ok, verify_reason = verify(name, params, before, after, extras)
            return _response(request, True, True, ok, None if ok else verify_reason, before, after, started)

        timeout_s = float(meta["timeout_s"])
        attempts = int(meta["retry"]) + 1
        deadline = started + timeout_s
        last_error = None
        after = before
        token = None
        executed = False
        for _attempt in range(attempts):
            if time.monotonic() >= deadline:
                break
            try:
                token = self.execute(name, params)
                executed = True
            except Exception as exc:
                last_error = str(exc)
                continue
            after, extras, ok, last_error = self._poll_verify(name, params, before, deadline)
            if ok:
                return _response(request, True, True, True, None, before, after, started)
            if token is not None:
                try:
                    self.rollback(name, token)
                except Exception as exc:
                    last_error = f"verify 失败且 rollback 失败：{exc}"
        error = last_error or "动作未通过 verify"
        return _response(request, True, executed, False, error, before, after, started)

    def _poll_verify(self, name, params, before, deadline):
        last = before
        extras = self.extras()
        reason = "verify 超时"
        while time.monotonic() < deadline:
            last = self.snapshot()
            extras = self.extras()
            ok, reason = verify(name, params, before, last, extras)
            if ok:
                return last, extras, True, None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.15, remaining))
        return last, extras, False, reason


def _response(request, accepted, executed, verified, error, before, after, started):
    return {
        "request_id": request["request_id"],
        "accepted": accepted,
        "executed": executed,
        "verified": verified,
        "error": error,
        "snapshot_before": before,
        "snapshot_after": after,
        "duration_ms": round((time.monotonic() - started) * 1000.0, 1),
    }


def _make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            del format, args

        def _write(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path != "/api/state":
                self._write(404, {"error": "not found"})
                return
            try:
                self._write(200, service.snapshot())
            except Exception as exc:
                self._write(500, {"error": str(exc)})

        def do_POST(self):
            path = urlparse(self.path).path
            if path != "/api/action":
                self._write(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._write(400, {"error": "invalid json"})
                return
            try:
                self._write(200, service.run_action(payload))
            except ActionError as exc:
                self._write(400, {"error": str(exc)})
            except Exception as exc:
                self._write(500, {"error": str(exc)})

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_control_api(runtime, host="127.0.0.1", port=8787):
    if not port:
        return None
    service = ControlService(runtime)
    server = _Server((host, int(port)), _make_handler(service))
    thread = threading.Thread(target=server.serve_forever, name="gearpro-control", daemon=True)
    thread.start()
    server.thread = thread
    print(f"Control API http://{host}:{server.server_address[1]}/api/state")
    return server
