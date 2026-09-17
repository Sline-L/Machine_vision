#!/usr/bin/env python3
"""HTTP ops-chain for GUI ↔ Agent (no browser). Requires isolated dual Web + Agent.

Covers: login → acquire → start inspection (monitor) → agent status →
arm (only if execute_replay) → optional pause/wait for cycle → stop (disarm) .
Records whether browser manual QA is still required.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


def _opener():
    jar = CookieJar()
    return build_opener(HTTPCookieProcessor(jar)), jar


def _json(opener, method, url, body=None, timeout=8.0):
    raw = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    # Empty POST bodies still need a method POST without Content-Type issues
    if method == "POST" and body is None:
        raw = b"{}"
        headers = {"Content-Type": "application/json"}
    req = Request(url, data=raw, method=method, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body_txt = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body_txt)
        except json.JSONDecodeError:
            payload = {"error": body_txt}
        return exc.code, payload
    except (URLError, TimeoutError, OSError) as exc:
        return 599, {"error": str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", default="http://127.0.0.1:8001")
    parser.add_argument("--agent-url", default="http://127.0.0.1:8790")
    parser.add_argument("--control-url", default="http://127.0.0.1:8788")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--expect-execute-mode", default="execute_replay")
    args = parser.parse_args(argv)

    web = args.web_url.rstrip("/")
    evidence = {
        "protocol": "p0-gui-ops-chain-v1",
        "web_url": web,
        "agent_url": args.agent_url,
        "browser_manual_qa": "NOT_RUN",
        "steps": {},
    }
    opener, _jar = _opener()

    code, login = _json(opener, "POST", f"{web}/api/v1/session/login", {"password": "", "label": "p0-gui-ops"})
    evidence["steps"]["login"] = {"http": code, "authenticated": (login or {}).get("authenticated")}
    if code >= 400:
        evidence["result"] = "FAIL_LOGIN"
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        return 2

    code, acq = _json(opener, "POST", f"{web}/api/v1/control/acquire", {})
    evidence["steps"]["acquire"] = {"http": code, "is_owner": (acq or {}).get("is_owner") or (acq or {}).get("control", {}).get("is_owner")}

    code, start = _json(opener, "POST", f"{web}/api/v1/inspection/start", {}, timeout=60.0)
    evidence["steps"]["inspection_start"] = {"http": code, "ok": code < 400}
    time.sleep(1.0)
    code, status = _json(opener, "GET", f"{web}/api/v1/agent/status")
    evidence["steps"]["agent_status_after_start"] = {
        "http": code,
        "monitoring": (status or {}).get("monitoring"),
        "recovery_armed": (status or {}).get("recovery_armed"),
        "llm_ready": (status or {}).get("llm_ready"),
        "execution_mode": (status or {}).get("execution_mode"),
        "last_cycle_route": ((status or {}).get("last_cycle") or {}).get("route"),
    }

    # Arm: expect success only when agent execute_replay
    code, arm = _json(opener, "POST", f"{web}/api/v1/agent/recovery/arm", {})
    evidence["steps"]["arm"] = {
        "http": code,
        "recovery_armed": (arm or {}).get("recovery_armed"),
        "execution_mode": (arm or {}).get("execution_mode"),
        "error": (arm or {}).get("error") or (arm or {}).get("detail"),
    }

    # Induce pause via Control so armed agent can recover (if execute_replay)
    from urllib.request import urlopen

    pause_payload = json.dumps(
        {"name": "pause_inspection", "params": {}, "source": "human", "request_id": f"gui-ops-pause-{uuid.uuid4().hex[:8]}"}
    ).encode("utf-8")
    try:
        with urlopen(
            Request(args.control_url.rstrip("/") + "/api/action", data=pause_payload, headers={"Content-Type": "application/json"}, method="POST"),
            timeout=30,
        ) as resp:
            pause = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError) as exc:
        pause = {"error": str(exc)}
    evidence["steps"]["induced_pause"] = {k: pause.get(k) for k in ("accepted", "executed", "verify_level", "error", "request_id")}

    recovered = False
    last = None
    # Keep control lease alive during wait
    for _ in range(20):
        time.sleep(2.0)
        _json(opener, "POST", f"{web}/api/v1/control/acquire", {})
        code, last = _json(opener, "GET", f"{web}/api/v1/agent/status")
        cycle = (last or {}).get("last_cycle") or {}
        if cycle.get("actually_executed") and cycle.get("recovery_outcome") == "RECOVERED":
            recovered = True
            break
        if cycle.get("actually_executed") and (cycle.get("verify_level") or "") != "none":
            # executed with some verify — accept for ops-chain
            recovered = cycle.get("recovery_outcome") == "RECOVERED"
            if recovered:
                break
    evidence["steps"]["wait_cycle"] = {
        "recovered": recovered,
        "monitoring": (last or {}).get("monitoring"),
        "recovery_armed": (last or {}).get("recovery_armed"),
        "last_cycle": {
            "fault": (last or {}).get("last_cycle", {}).get("fault") if last else None,
            "route": ((last or {}).get("last_cycle") or {}).get("route"),
            "proposed_action": ((last or {}).get("last_cycle") or {}).get("proposed_action"),
            "authority_decision": ((last or {}).get("last_cycle") or {}).get("authority_decision"),
            "actually_executed": ((last or {}).get("last_cycle") or {}).get("actually_executed"),
            "verify_level": ((last or {}).get("last_cycle") or {}).get("verify_level"),
            "recovery_outcome": ((last or {}).get("last_cycle") or {}).get("recovery_outcome"),
            "l2": ((last or {}).get("last_cycle") or {}).get("l2"),
            "control_result": {
                k: (((last or {}).get("last_cycle") or {}).get("control_result") or {}).get(k)
                for k in ("request_id", "executed", "verify_level", "recovery_success", "error")
            },
        },
    }

    code, stop = _json(opener, "POST", f"{web}/api/v1/inspection/stop", {}, timeout=60.0)
    evidence["steps"]["inspection_stop"] = {"http": code, "ok": code < 400}
    time.sleep(0.8)
    code, after_stop = _json(opener, "GET", f"{web}/api/v1/agent/status")
    evidence["steps"]["agent_status_after_stop"] = {
        "http": code,
        "monitoring": (after_stop or {}).get("monitoring"),
        "recovery_armed": (after_stop or {}).get("recovery_armed"),
    }

    mode = (evidence["steps"]["agent_status_after_start"].get("execution_mode") or "")
    start_ok = evidence["steps"]["agent_status_after_start"].get("monitoring") is True
    start_not_armed = evidence["steps"]["agent_status_after_start"].get("recovery_armed") is False
    stop_disarmed = evidence["steps"]["agent_status_after_stop"].get("recovery_armed") is False
    stop_unmonitored = evidence["steps"]["agent_status_after_stop"].get("monitoring") is False
    llm_ok = evidence["steps"]["agent_status_after_start"].get("llm_ready") is True

    if mode == "execute_replay":
        arm_ok = evidence["steps"]["arm"].get("http") == 200 and evidence["steps"]["arm"].get("recovery_armed") is True
        # L1 may recover before L2 when armed — either is valid for GUI ops chain.
        exec_ok = recovered or bool((evidence["steps"]["wait_cycle"]["last_cycle"] or {}).get("actually_executed"))
        evidence["result"] = "PASS" if (start_ok and start_not_armed and arm_ok and stop_disarmed and stop_unmonitored and llm_ok) else "FAIL"
        evidence["execute_path"] = "execute_replay_armed"
        evidence["recovery_seen"] = exec_ok
    else:
        arm_rejected = evidence["steps"]["arm"].get("http") in (409, 403, 400, 503)
        evidence["result"] = "PASS" if (start_ok and start_not_armed and arm_rejected and stop_disarmed and stop_unmonitored and llm_ok) else "FAIL"
        evidence["execute_path"] = "observe_only_arm_rejected"
        evidence["note"] = "observe_only correctly refused arm; start separate execute_replay agent for recovery demo"

    evidence["claims"] = {
        "monitor_on_start_without_arm": start_ok and start_not_armed,
        "llm_ready_visible": llm_ok,
        "stop_disarms_and_stops_monitor": stop_disarmed and stop_unmonitored,
        "browser_manual_qa": "NOT_RUN",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": evidence["result"], "claims": evidence["claims"], "execute_path": evidence.get("execute_path"), "recovery_seen": evidence.get("recovery_seen")}, indent=2))
    print(f"wrote {args.json_out}")
    return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
