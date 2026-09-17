"""Standalone EdgeMedic Agent service (HTTP status + monitor loop).

Monitoring is NOT full execute authority.
Default execution_mode=observe_only.
Operator inspection/stop notifies /monitor/stop (disarm + stop monitor).
Fault pause must NOT auto-disarm — recovery needs the armed window.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .runtime import EXECUTE_OBSERVE, EXECUTE_REPLAY, LoopState, make_client, run_once


class AgentServiceState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = True
        self.monitoring = False
        self.recovery_armed = False
        self.llm_ready = False
        self.last_cycle = None
        self.last_error = None
        self.started_at = time.time()
        self.ticks = 0
        self.control_url = ""
        self.llm_url = ""
        self.execution_mode = EXECUTE_OBSERVE
        self.pid = os.getpid()

    def snapshot(self):
        with self.lock:
            return {
                "service": "edgemedic-agent",
                "pid": self.pid,
                "uptime_s": round(time.time() - self.started_at, 1),
                "running": self.running,
                "monitoring": self.monitoring,
                "recovery_armed": self.recovery_armed,
                "execution_mode": self.execution_mode,
                "llm_ready": self.llm_ready,
                "llm_url": self.llm_url,
                "control_url": self.control_url,
                "ticks": self.ticks,
                "last_error": self.last_error,
                "last_cycle": self.last_cycle,
                "note": "monitoring≠auto-execute; recovery_armed requires explicit execute_replay + pipeline active",
            }


STATE = AgentServiceState()


def _probe_llm(llm_url):
    if not llm_url:
        return False
    try:
        from urllib.request import urlopen

        with urlopen(llm_url.rstrip("/") + "/v1/models", timeout=2.0) as response:
            return response.status == 200
    except Exception:
        return False


def monitor_loop(interval):
    state = LoopState()
    while STATE.running:
        try:
            STATE.llm_ready = _probe_llm(STATE.llm_url)
            # Fault pause (inspection_active=False) must NOT disarm recovery —
            # that is exactly when resume is needed. Operator stop calls /monitor/stop.
            with STATE.lock:
                monitoring = STATE.monitoring
                mode = STATE.execution_mode
                armed = STATE.recovery_armed and mode == EXECUTE_REPLAY

            if not monitoring:
                time.sleep(interval)
                continue

            exec_mode = EXECUTE_REPLAY if armed else EXECUTE_OBSERVE
            client = make_client(STATE.control_url, exec_mode)
            if not STATE.llm_ready:
                with STATE.lock:
                    STATE.last_error = "llm_not_ready"
                    STATE.last_cycle = {
                        "fault": None,
                        "route": {"selected": None},
                        "note": "4B service not ready; tick skipped mutate",
                        "llm_ready": False,
                    }
                time.sleep(interval)
                continue

            cycle = run_once(
                client,
                state,
                llm_url=STATE.llm_url,
                execution_mode=exec_mode,
                disable_memory=False,
            )
            with STATE.lock:
                STATE.ticks += 1
                STATE.last_cycle = cycle
                STATE.last_error = None
        except Exception as exc:
            with STATE.lock:
                STATE.last_error = str(exc)
        time.sleep(interval)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[agent-service] " + (fmt % args) + "\n")

    def _json(self, code, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/health", "/api/health"):
            self._json(200, {"ok": True, "pid": STATE.pid, "llm_ready": STATE.llm_ready})
            return
        if self.path in ("/status", "/api/status"):
            self._json(200, STATE.snapshot())
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if self.path in ("/monitor/start", "/api/monitor/start"):
            with STATE.lock:
                STATE.monitoring = True
                # Arm recovery only when explicitly requested AND execute_replay mode.
                if payload.get("arm_recovery") and STATE.execution_mode == EXECUTE_REPLAY:
                    STATE.recovery_armed = True
            self._json(200, STATE.snapshot())
            return
        if self.path in ("/monitor/stop", "/api/monitor/stop"):
            with STATE.lock:
                STATE.monitoring = False
                STATE.recovery_armed = False
            self._json(200, STATE.snapshot())
            return
        if self.path in ("/recovery/arm", "/api/recovery/arm"):
            with STATE.lock:
                if STATE.execution_mode != EXECUTE_REPLAY:
                    self._json(
                        409,
                        {
                            "error": "agent execution_mode is not execute_replay; refuse arm",
                            "execution_mode": STATE.execution_mode,
                            "note": "isolation: production observe_only cannot arm recovery",
                        },
                    )
                    return
                if "8787" in (STATE.control_url or ""):
                    self._json(403, {"error": "refusing arm against control :8787"})
                    return
                STATE.monitoring = True
                STATE.recovery_armed = True
            self._json(200, STATE.snapshot())
            return
        if self.path in ("/recovery/disarm", "/api/recovery/disarm"):
            with STATE.lock:
                STATE.recovery_armed = False
            self._json(200, STATE.snapshot())
            return
        if self.path in ("/shutdown", "/api/shutdown"):
            with STATE.lock:
                STATE.running = False
                STATE.monitoring = False
                STATE.recovery_armed = False
            self._json(200, {"ok": True, "stopping": True})
            threading.Thread(target=lambda: (time.sleep(0.2), os.kill(os.getpid(), signal.SIGTERM)), daemon=True).start()
            return
        self._json(404, {"error": "not_found"})


_PIDFILE = None


def _write_pid(path):
    global _PIDFILE
    _PIDFILE = Path(path)
    if _PIDFILE.exists():
        try:
            old = int(_PIDFILE.read_text().strip())
            os.kill(old, 0)
            raise SystemExit(f"agent already running pid={old} ({_PIDFILE})")
        except (ValueError, ProcessLookupError, OSError):
            pass
    _PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    _PIDFILE.write_text(str(os.getpid()), encoding="utf-8")


def _clear_pid():
    if _PIDFILE and _PIDFILE.exists():
        try:
            if int(_PIDFILE.read_text().strip()) == os.getpid():
                _PIDFILE.unlink()
        except Exception:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic Agent service")
    parser.add_argument("--control-url", default=os.getenv("EDGEMEDIC_CONTROL_URL", "http://127.0.0.1:8788"))
    parser.add_argument("--llm-url", default=os.getenv("EDGEMEDIC_LLM_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--status-host", default="127.0.0.1")
    parser.add_argument("--status-port", type=int, default=int(os.getenv("EDGEMEDIC_STATUS_PORT", "8790")))
    parser.add_argument("--execution-mode", choices=(EXECUTE_OBSERVE, EXECUTE_REPLAY), default=os.getenv("EDGEMEDIC_EXECUTION_MODE", EXECUTE_OBSERVE))
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--pidfile", default=os.getenv("EDGEMEDIC_PIDFILE", ".cache/edgemedic/agent.pid"))
    parser.add_argument("--auto-monitor", action="store_true", help="start monitoring on boot (still observe-only unless armed)")
    args = parser.parse_args(argv)

    if "8787" in args.control_url and args.execution_mode == EXECUTE_REPLAY:
        raise SystemExit("refusing execute_replay against :8787")

    _write_pid(args.pidfile)
    STATE.control_url = args.control_url
    STATE.llm_url = args.llm_url
    STATE.execution_mode = args.execution_mode
    STATE.llm_ready = _probe_llm(args.llm_url)
    if args.auto_monitor:
        STATE.monitoring = True
        # Do not auto-arm recovery.

    def _stop(*_args):
        STATE.running = False
        STATE.monitoring = False
        STATE.recovery_armed = False
        _clear_pid()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    worker = threading.Thread(target=monitor_loop, args=(args.interval,), daemon=True)
    worker.start()
    server = ThreadingHTTPServer((args.status_host, args.status_port), Handler)
    server.timeout = 0.5
    print(
        f"EdgeMedic agent service on {args.status_host}:{args.status_port} "
        f"mode={args.execution_mode} control={args.control_url} llm_ready={STATE.llm_ready}"
    )
    try:
        while STATE.running:
            server.handle_request()
    finally:
        _clear_pid()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
