#!/usr/bin/env python3
"""P0 final: inject pause only; resident Agent recovers. Never run_once."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

OUT = Path("/home/jetson/Projects/p0-4b-agent/docs/midterm/runs/p0/final_system")
AGENT = "http://127.0.0.1:8790"
CONTROL = "http://127.0.0.1:8788"
LOG = Path("/tmp/edgemedic-agent.log")


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.load(resp)


def post_action(name, request_id):
    """Fault injection only — never resume/restart (Agent owns recovery)."""
    if name not in ("pause_inspection",):
        raise SystemExit(f"inject refuses non-fault action: {name}")
    payload = json.dumps(
        {"name": name, "params": {}, "source": "p0_final_inject", "request_id": request_id}
    ).encode("utf-8")
    req = urllib.request.Request(
        CONTROL + "/api/action",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def mission_active():
    d = get_json(CONTROL + "/api/state")
    m = d.get("mission") or {}
    return bool(m.get("inspection_active")), d


def summarize(status):
    lc = status.get("last_cycle") or {}
    cr = lc.get("control_result") or {}
    l2 = lc.get("l2") or {}
    return {
        "monitoring": status.get("monitoring"),
        "armed": status.get("recovery_armed"),
        "mode": status.get("execution_mode"),
        "fault": lc.get("fault"),
        "route": (lc.get("route") or {}).get("selected"),
        "route_full": lc.get("route"),
        "l2_invoked": bool(l2.get("invoked")),
        "model": l2.get("model"),
        "raw_preview": l2.get("raw_preview"),
        "l2_latency_ms": l2.get("latency_ms"),
        "proposed": lc.get("proposed_action"),
        "authority": lc.get("authority_decision"),
        "executed": lc.get("actually_executed"),
        "verify": lc.get("verify_level"),
        "outcome": lc.get("recovery_outcome"),
        "request_id": cr.get("request_id"),
        "control_result": cr,
        "last_cycle": lc,
    }


def poll(want, timeout=90.0, label=""):
    deadline = time.time() + timeout
    samples = []
    while time.time() < deadline:
        st = get_json(AGENT + "/status")
        row = summarize(st)
        slim = {
            k: row[k]
            for k in (
                "armed",
                "fault",
                "route",
                "l2_invoked",
                "model",
                "executed",
                "verify",
                "outcome",
                "request_id",
            )
        }
        samples.append(slim)
        print(f"[{label}] {slim}", flush=True)
        lc = row["last_cycle"]
        l2 = lc.get("l2") or {}
        if want == "l1_resume":
            if (
                row["route"] == "L1"
                and (row["proposed"] or {}).get("name") == "resume_inspection"
                and row["executed"]
                and row["outcome"] == "RECOVERED"
            ):
                return row, samples
        elif want == "l2_recovered":
            if (
                row["route"] == "L2"
                and bool(l2.get("invoked"))
                and row["executed"]
                and row["outcome"] == "RECOVERED"
                and (row["proposed"] or {}).get("name") == "resume_inspection"
            ):
                return row, samples
        time.sleep(0.5)
    return None, samples


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pre = get_json(AGENT + "/status")
    if not pre.get("recovery_armed"):
        raise SystemExit("NOT_ARMED")
    if pre.get("execution_mode") != "execute_replay":
        raise SystemExit("bad mode")
    if "8787" in (pre.get("control_url") or ""):
        raise SystemExit("refuse 8787")
    active, _ = mission_active()
    if not active:
        raise SystemExit("inspection not active — GUI must start pipeline first")

    log_offset = LOG.stat().st_size if LOG.exists() else 0
    evidence = {
        "protocol": "p0-final-system-resident-agent-pause-v1",
        "pre": summarize(pre),
        "phases": {},
        "note": "inject=pause_inspection only; resident edgemedic.service owns resume",
    }

    # Phase A: inject pause -> resident L1 resume (cooldown seed)
    print("PHASE_A inject pause for L1", flush=True)
    inj_a = post_action("pause_inspection", "INJECT-A-pause")
    evidence["phases"]["A_inject"] = {
        "accepted": inj_a.get("accepted"),
        "executed": inj_a.get("executed"),
        "request_id": inj_a.get("request_id"),
        "error": inj_a.get("error"),
    }
    active, _ = mission_active()
    evidence["phases"]["A_paused"] = {"inspection_active": active}
    if active:
        evidence["result"] = "FAIL"
        evidence["breakpoint"] = "pause_inspection inject did not pause mission"
        _finalize(evidence, log_offset)
        return 3

    hit_a, samples_a = poll("l1_resume", timeout=40, label="A")
    evidence["phases"]["A_l1"] = {
        "hit": None if hit_a is None else {k: hit_a[k] for k in hit_a if k != "last_cycle"},
        "samples": samples_a,
    }
    if hit_a and hit_a.get("last_cycle"):
        (OUT / "phase_a_l1_cycle.json").write_text(
            json.dumps(hit_a["last_cycle"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if not hit_a:
        evidence["result"] = "FAIL"
        evidence["breakpoint"] = "resident Agent did not L1-resume after pause inject"
        _finalize(evidence, log_offset)
        return 4

    # Phase B: re-pause inside INSPECTION_PAUSED L1 cooldown -> natural L2 + 4B
    print("PHASE_B re-pause within L1 cooldown for natural L2", flush=True)
    t0 = time.time()
    inj_b = post_action("pause_inspection", "INJECT-B-pause")
    evidence["phases"]["B_inject"] = {
        "accepted": inj_b.get("accepted"),
        "executed": inj_b.get("executed"),
        "request_id": inj_b.get("request_id"),
        "error": inj_b.get("error"),
        "t_after_l1_s": round(time.time() - t0, 3),
    }
    active, _ = mission_active()
    if active:
        evidence["result"] = "FAIL"
        evidence["breakpoint"] = "second pause inject failed; mission still active"
        _finalize(evidence, log_offset)
        return 5

    # Stay inside ~10s L1 cooldown; L2 inference may take a few seconds.
    hit_b, samples_b = poll("l2_recovered", timeout=25, label="B")
    evidence["phases"]["B_l2"] = {
        "hit": None if hit_b is None else {k: hit_b[k] for k in hit_b if k != "last_cycle"},
        "samples": samples_b,
        "elapsed_s": round(time.time() - t0, 3),
    }
    if hit_b:
        evidence["l2_hit"] = {k: hit_b[k] for k in hit_b if k != "last_cycle"}
        evidence["l2_last_cycle"] = hit_b.get("last_cycle")
        evidence["request_id"] = hit_b.get("request_id")
        evidence["result"] = "PASS"
        (OUT / "last_cycle.json").write_text(
            json.dumps(hit_b.get("last_cycle"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        evidence["l2_last_cycle"] = summarize(get_json(AGENT + "/status")).get("last_cycle")
        evidence["result"] = "FAIL"
        evidence["breakpoint"] = (
            "resident Agent did not complete L2+4B resume Execute+Verify after second pause; "
            "see B_l2 samples (L1 cooldown expired, L2 cooldown, or abstain)"
        )
    _finalize(evidence, log_offset)
    return 0 if evidence["result"] == "PASS" else 6


def _finalize(evidence, log_offset):
    evidence["post_agent"] = summarize(get_json(AGENT + "/status"))
    active, state = mission_active()
    evidence["post_mission_active"] = active
    if LOG.exists():
        data = LOG.read_bytes()[log_offset:]
        (OUT / "agent_service.log_slice.txt").write_bytes(data)
        evidence["agent_log_slice_bytes"] = len(data)
    (OUT / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "RESULT",
        evidence.get("result"),
        "request_id=",
        evidence.get("request_id"),
        "breakpoint=",
        evidence.get("breakpoint"),
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
