"""Synthetic experiment runner: detect → incident → recover → score → reset."""

from pathlib import Path
import argparse
import json
import time

from edgemedic.bench import load_cases, merge_state, run_suite
from edgemedic.incident import build_incident
from edgemedic.policy import Memory, classify_fault, decide


def run_inject(cases=None):
    """Stage-1 software path: snapshot in, decision out. No camera required."""
    rows = []
    for case in cases or load_cases():
        snapshot = merge_state(case.get("state"))
        memory = Memory()
        t0 = time.monotonic()
        fault = classify_fault(snapshot, memory)
        mttd_ms = round((time.monotonic() - t0) * 1000.0, 3)
        t1 = time.monotonic()
        action = decide(snapshot, memory)
        mttr_ms = round((time.monotonic() - t1) * 1000.0, 3)
        incident = build_incident(fault or case.get("fault"), snapshot, action, None if action is None else action.get("layer"))
        expected = case.get("expected_verify_level")
        rows.append(
            {
                "case": case.get("case"),
                "fault": fault,
                "mttd_ms": mttd_ms,
                "mttr_decide_ms": mttr_ms,
                "action": None if action is None else {"name": action.get("name"), "params": action.get("params")},
                "incident": incident,
                "expected_verify_level": expected,
            }
        )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic synthetic experiment")
    parser.add_argument("--reasoner", choices=("mock", "qwen"), default="mock")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--l2-always", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    inject = run_inject()
    bench = run_suite(reasoner=args.reasoner, llm_url=args.llm_url, l2_always=args.l2_always)
    payload = {
        "inject": inject,
        "bench": {key: value for key, value in bench.items() if key != "rows"},
        "bench_rows": bench.get("rows"),
        "asr_note": "ASR_func / ASR_mission need live GearPro cycle windows; this runner reports decision metrics only.",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if bench.get("unsafe_action_leakage") == 0.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
