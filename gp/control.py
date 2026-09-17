"""Control API: accept / execute / three-level verify / rollback."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from urllib.parse import urlparse

from .actions import LKG_ACTIONS, SPECS, ActionError, accept, bind_source, parse_request
from .control_view import cap_verify_level
from .verify import assess, can_reach_function, can_reach_mission, config_verified


class ControlService:
    def __init__(self, runtime):
        self.runtime = runtime

    def snapshot(self):
        return self.runtime.current_snapshot()

    def extras(self):
        return self.runtime.control_extras()

    def execute(self, name, params):
        return self.runtime.execute_action(name, params, authority=getattr(self, "_authority", None))

    def rollback(self, name, token):
        return self.runtime.rollback_action(name, token)

    def run_action(self, body, authority="agent"):
        started = time.monotonic()
        dry_run = bool(body.get("dry_run"))
        overlay = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else None
        request = parse_request(body)
        request["authority"] = authority
        request["source"] = bind_source(request.get("declared_source"), authority)
        self._authority = authority
        name = request["name"]
        params = request["params"]
        meta = SPECS[name]
        before = self.snapshot()
        if overlay:
            before = _overlay_snapshot(before, overlay)
        extras = self.extras()
        extras["source"] = request["source"]
        extras["authority"] = authority
        allowed, reason = accept(name, params, before, extras, source=request["source"])
        if dry_run:
            code, precondition = _guardian_codes(name, allowed, reason)
            return {
                "request_id": request["request_id"],
                "accepted": allowed,
                "executed": False,
                "dry_run": True,
                "guardian_decision": "approve" if allowed else "reject",
                "reason": reason,
                "reason_code": code,
                "precondition": precondition,
                "verify_level": "none",
                "authority": request.get("authority"),
                "source": request.get("source"),
                "error": None if allowed else reason,
                "snapshot_before": before,
                "snapshot_after": before,
                "duration_ms": round((time.monotonic() - started) * 1000.0, 1),
            }
        if not allowed:
            return _response(request, False, False, "none", reason, before, before, started, extras)
        if name == "get_state":
            after = before
            level, verify_reason = _assess(name, params, before, after, extras)
            return _response(request, True, True, level, None if config_verified(level) else verify_reason, before, after, started, extras)

        timeout_s = float(meta["timeout_s"])
        attempts = int(meta["retry"]) + 1
        deadline = started + timeout_s
        last_error = None
        after = before
        token = None
        executed = False
        level = "none"
        for _attempt in range(attempts):
            if time.monotonic() >= deadline:
                break
            try:
                token = self.execute(name, params)
                executed = True
            except Exception as exc:
                last_error = str(exc)
                continue
            after, extras, level, last_error = self._poll_verify(name, params, before, deadline)
            if config_verified(level):
                self._maybe_promote_lkg(name, level)
                return _response(request, True, True, level, last_error, before, after, started, extras)
            if token is not None:
                try:
                    self.rollback(name, token)
                except Exception as exc:
                    last_error = f"verify 失败且 rollback 失败：{exc}"
        error = last_error or "动作未通过 verify"
        return _response(request, True, executed, level, error, before, after, started, extras)

    def _poll_verify(self, name, params, before, deadline):
        last = before
        extras = self.extras()
        reason = "verify 超时"
        best_level = "none"
        best_reason = reason
        while time.monotonic() < deadline:
            last = self.snapshot()
            extras = self.extras()
            level, reason = _assess(name, params, before, last, extras)
            if _better(level, best_level):
                best_level = level
                best_reason = reason
            if extras.get("emergency_hold") and name not in ("pause_inspection",) and not (
                name == "set_inference_profile" and (params or {}).get("profile") == "SAFE_STOP"
            ):
                held = best_level if config_verified(best_level) else "none"
                return last, extras, held, reason or "紧急停机中断恢复"
            if level == "mission":
                return last, extras, level, None
            if level == "function" and not can_reach_mission(name, params, extras):
                return last, extras, level, None
            if config_verified(level):
                waiting_for_dual = (
                    can_reach_function(extras)
                    and extras.get("specialists_loaded")
                    and not extras.get("dual_specialist_evidence")
                    and name not in ("pause_inspection", "apply_settings", "get_state", "reset_stats", "reconnect_serial")
                    and not (name == "set_inference_profile" and (params or {}).get("profile") == "SAFE_STOP")
                )
                waiting_for_window = (
                    level == "function"
                    and can_reach_mission(name, params, extras)
                    and extras.get("dual_specialist_evidence")
                )
                if not waiting_for_dual and not waiting_for_window:
                    return last, extras, level, reason
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.15, remaining))
        note = None if config_verified(best_level) else (best_reason or reason)
        return last, extras, best_level, note

    def _maybe_promote_lkg(self, name, level):
        if name not in LKG_ACTIONS:
            return
        if not config_verified(level):
            return
        promote = getattr(self.runtime, "promote_last_known_good", None)
        if callable(promote):
            try:
                promote()
            except OSError:
                pass


def _assess(name, params, before, after, extras):
    level, reason = assess(name, params, before, after, extras)
    capped, note = cap_verify_level(name, params, level, extras)
    if note:
        return capped, note
    return capped, reason


def _overlay_snapshot(base, overlay):
    out = dict(base or {})
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def _guardian_codes(name, allowed, reason):
    if allowed:
        return None, None
    text = reason or ""
    if name == "restart_worker" and "未异常" in text:
        return "worker_not_failed", "worker_failure_required"
    if name == "restart_camera" and "STALE" in text:
        return "camera_not_stale", "camera_failure_required"
    if name == "reconnect_serial" and "已连接" in text:
        return "serial_healthy", "serial_failure_required"
    return "precondition_failed", name


def _better(left, right):
    order = {"none": 0, "config": 1, "function": 2, "mission": 3}
    return order.get(left, 0) > order.get(right, 0)


def _response(request, accepted, executed, verify_level, error, before, after, started, extras=None):
    from .control_view import inspection_recovery_success

    extras = extras or {}
    recovered = inspection_recovery_success(request.get("name"), request.get("params"), verify_level, extras)
    configured = config_verified(verify_level)
    return {
        "request_id": request["request_id"],
        "accepted": accepted,
        "executed": executed,
        "verified": recovered,
        "config_verified": configured,
        "recovery_success": recovered,
        "function_verified": verify_level in ("function", "mission"),
        "mission_verified": verify_level == "mission",
        "verify_level": verify_level,
        "authority": request.get("authority"),
        "source": request.get("source"),
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
                self._write(200, service.run_action(payload, authority="agent"))
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
