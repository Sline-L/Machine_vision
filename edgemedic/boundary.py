"""Q2 decision-boundary sweep: vary SystemSnapshot evidence only.

Same Qwen3-4B prompt, GBNF, temperature, max_tokens, and scorer as Q1.
Does not encode the correct tool in the grammar.
"""

from pathlib import Path
import argparse
import json

from edgemedic.bench import run_suite
from edgemedic.reasoner import DECODE_GRAMMAR

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"

# Q1 composite used 178 ms / locator.health 0.3 / healthy camera and V5 / backend pt.
LATENCIES_MS = (110, 130, 160, 178, 200)
Q1_LOCATOR_HEALTH = 0.3
Q1_V5_MS = 72.0
Q1_CAMERA_HEALTH = 1.0


def locator_overload_state(latency_ms, v5_ms=Q1_V5_MS, camera_health=Q1_CAMERA_HEALTH, backend="pt"):
    camera = {"health": float(camera_health)}
    if float(camera_health) < 1.0:
        camera["frame_age_ms"] = 800
    return {
        "locator": {
            "backend": backend,
            "loaded": True,
            "latency_ms": float(latency_ms),
            "health": Q1_LOCATOR_HEALTH,
        },
        "scratch_v5": {"total_latency_ms": float(v5_ms), "health": 1.0 if float(v5_ms) < 200 else 0.3},
        "camera": camera,
    }


def latency_cases():
    cases = []
    for latency in LATENCIES_MS:
        below = latency < 120
        cases.append(
            {
                "case": f"locator_latency_{int(latency)}",
                "family": "known-composite",
                "fault": None if below else "LOCATOR_OVERLOAD",
                "expected_layer": "none",
                "state": locator_overload_state(latency),
                "acceptable_actions": []
                if below
                else [{"tool": "set_locator_profile", "params": {"profile": "trt_fast"}}],
                "abstain_allowed": True,
                "expect_l2": "abstain" if below else None,
            }
        )
    return cases


def summarize_boundary(rows):
    table = {}
    for row in rows:
        key = row.get("case")
        bucket = table.setdefault(key, {"n": 0, "abstain": 0, "trt_fast": 0, "other": {}})
        bucket["n"] += 1
        l2 = row.get("l2") or {}
        action = l2.get("action") or {}
        if l2.get("abstain") and not action:
            bucket["abstain"] += 1
        elif action.get("name") == "set_locator_profile" and (action.get("params") or {}).get("profile") == "trt_fast":
            bucket["trt_fast"] += 1
        else:
            label = action.get("name") or "unknown"
            profile = (action.get("params") or {}).get("profile")
            if profile:
                label = f"{label}:{profile}"
            bucket["other"][label] = bucket["other"].get(label, 0) + 1
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description="Q2 locator evidence sweep")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--out", type=Path, default=RESULTS_ROOT / "qwen_q2_boundary.json")
    args = parser.parse_args(argv)
    summary = run_suite(
        reasoner="qwen",
        llm_url=args.llm_url,
        runs=args.runs,
        decode=DECODE_GRAMMAR,
        cases=latency_cases(),
    )
    payload = {
        "stage": "q2-decision-boundary",
        "axis": "locator.latency_ms",
        "held_constant": {
            "prompt": True,
            "grammar": True,
            "temperature": 0.0,
            "max_tokens": 160,
            "locator.health": Q1_LOCATOR_HEALTH,
            "scratch_v5.total_latency_ms": Q1_V5_MS,
            "camera.health": Q1_CAMERA_HEALTH,
            "locator.backend": "pt",
        },
        "latencies_ms": list(LATENCIES_MS),
        "boundary_table": summarize_boundary(summary.get("rows") or []),
        "protocol_compliance_rate": summary.get("protocol_compliance_rate"),
        "decision_accuracy_given_valid": summary.get("decision_accuracy_given_valid"),
        "wrong_legal_action_rate": summary.get("wrong_legal_action_rate"),
        "confusion_matrix": summary.get("confusion_matrix"),
        "decision_latency_s_mean": summary.get("decision_latency_s_mean"),
        "provenance": summary.get("provenance"),
        "experimentally_validated": False,
        "rows": summary.get("rows"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = {key: value for key, value in payload.items() if key != "rows"}
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
