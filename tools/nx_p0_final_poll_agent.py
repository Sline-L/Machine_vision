#!/usr/bin/env python3
"""Poll resident Agent /status only. Never run_once / never POST recovery."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-url", default="http://127.0.0.1:8790")
    ap.add_argument("--json-out", required=True)
    ap.add_argument("--want", default="l2_recovered", choices=("l2_recovered", "l1_exec", "l2_any", "any_exec"))
    ap.add_argument("--timeout", type=float, default=90.0)
    args = ap.parse_args()
    if "8787" in args.agent_url:
        raise SystemExit("refuse")

    deadline = time.time() + args.timeout
    samples = []
    hit = None
    while time.time() < deadline:
        with urllib.request.urlopen(args.agent_url.rstrip("/") + "/status", timeout=5) as resp:
            d = json.load(resp)
        lc = d.get("last_cycle") or {}
        route = (lc.get("route") or {}).get("selected")
        cr = lc.get("control_result") or {}
        l2 = lc.get("l2") or {}
        pa = lc.get("proposed_action") or {}
        rid = cr.get("request_id")
        row = {
            "t": time.time(),
            "monitoring": d.get("monitoring"),
            "armed": d.get("recovery_armed"),
            "mode": d.get("execution_mode"),
            "fault": lc.get("fault"),
            "route": route,
            "l1_hit": (lc.get("route") or {}).get("l1_hit"),
            "l2_invoked": bool(l2.get("invoked")),
            "model": l2.get("model"),
            "raw_preview": (l2.get("raw_preview") or "")[:400],
            "proposed": pa,
            "authority": lc.get("authority_decision"),
            "executed": lc.get("actually_executed"),
            "verify": lc.get("verify_level"),
            "outcome": lc.get("recovery_outcome"),
            "request_id": rid,
            "control_accepted": cr.get("accepted"),
            "control_executed": cr.get("executed"),
            "control_error": cr.get("error"),
            "control_verify": cr.get("verify_level"),
        }
        samples.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        ok = False
        if args.want == "l2_recovered":
            ok = (
                route == "L2"
                and bool(l2.get("invoked"))
                and bool(lc.get("actually_executed"))
                and lc.get("recovery_outcome") == "RECOVERED"
            )
        elif args.want == "l1_exec":
            ok = route == "L1" and bool(lc.get("actually_executed"))
        elif args.want == "l2_any":
            ok = route == "L2" and bool(l2.get("invoked"))
        elif args.want == "any_exec":
            ok = bool(lc.get("actually_executed"))
        if ok:
            hit = row
            break
        time.sleep(1.0)

    payload = {"want": args.want, "hit": hit, "samples": samples[-40:], "result": "HIT" if hit else "TIMEOUT"}
    path = args.json_out
    open(path, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print("POLL_RESULT", payload["result"], "request_id=", (hit or {}).get("request_id"))
    raise SystemExit(0 if hit else 5)


if __name__ == "__main__":
    raise SystemExit(main())
