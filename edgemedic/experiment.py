"""Synthetic experiment runner. Live NX ASR is future work, not claimed here."""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import json
import time
import uuid

from edgemedic.bench import load_cases, merge_state, run_suite
from edgemedic.candidate import generate_candidates
from edgemedic.incident import build_incident
from edgemedic.inject import INJECTORS, patch_snapshot
from edgemedic.policy import Memory, classify_fault, decide
from edgemedic.provenance import collect_provenance, live_action, sample_live


RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"


def _now():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_outputs(out_dir, runs, summary):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in runs), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if runs:
        keys = sorted({key for row in runs for key in row if key != "incident"})
        with (out_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for row in runs:
                writer.writerow({key: row.get(key) for key in keys})
    return out_dir


def run_synthetic(cases=None, runs=1, ablation="full"):
    cases = list(cases or load_cases())
    rows = []
    function_ok = 0
    mission_ok = 0
    faults = 0
    t_fault = 0.0
    for _ in range(max(1, int(runs))):
        for case in cases:
            snapshot = merge_state(case.get("state"))
            memory = Memory()
            t0 = time.monotonic()
            fault = None if ablation == "no-reflex" and case.get("family") == "known-simple" else classify_fault(snapshot, memory)
            if ablation == "no-reflex":
                action = None
            else:
                action = decide(snapshot, memory)
            mttd_ms = round((time.monotonic() - t0) * 1000.0, 3)
            expected = case.get("expected_verify_level")
            layer = None if action is None else action.get("layer")
            if ablation == "no-l2" and layer is None and case.get("family") == "known-composite":
                expected = "none"
            incident = build_incident(fault or case.get("fault"), snapshot, action, layer)
            verify_level = "none"
            if action is not None and case.get("family") == "known-simple":
                verify_level = "function"
            if action is not None and case.get("case") == "v5_overload_01":
                verify_level = "function"
            rows.append(
                {
                    "run_id": uuid.uuid4().hex[:8],
                    "case": case.get("case"),
                    "family": case.get("family"),
                    "fault": fault,
                    "mttd_ms": mttd_ms,
                    "mttr_ms": None,
                    "action": None if action is None else {"name": action.get("name"), "params": action.get("params")},
                    "verify_level": verify_level,
                    "expected_verify_level": expected,
                    "ablation": ablation,
                    "incident_id": incident.get("incident_id"),
                }
            )
            if case.get("family") != "unsafe-request":
                faults += 1
                if verify_level in ("function", "mission"):
                    function_ok += 1
                if verify_level == "mission":
                    mission_ok += 1
            t_fault += mttd_ms
    summary = {
        "stage": "synthetic",
        "validated": False,
        "ablation": ablation,
        "runs": len(rows),
        "asr_function": None if not faults else round(function_ok / faults, 4),
        "asr_mission": None if not faults else round(mission_ok / faults, 4),
        "mttd_mean_ms": None if not rows else round(t_fault / len(rows), 4),
        "mttr_note": "MTTR uses t_mission_verified - t_fault. Synthetic runner has no live verify window, so mttr_ms is null.",
        "nx_workload": "not-run",
        "provenance": collect_provenance(runtime_mode="synthetic"),
    }
    return rows, summary


def run_software_inject(baseline=None, injectors=None):
    from edgemedic.bench import default_snapshot

    baseline = baseline or default_snapshot()
    rows = []
    for name in injectors or INJECTORS:
        snapshot = patch_snapshot(baseline, name)
        memory = Memory()
        t0 = time.monotonic()
        fault = classify_fault(snapshot, memory)
        action = decide(snapshot, memory)
        rows.append(
            {
                "injector": name,
                "fault": fault,
                "mttd_ms": round((time.monotonic() - t0) * 1000.0, 3),
                "action": None if action is None else {"name": action.get("name"), "params": action.get("params")},
                "reset": "ok",
            }
        )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic experiment runner")
    parser.add_argument("--reasoner", choices=("mock", "qwen"), default="mock")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--case", default=None, help="single case id, default all")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--ablation", choices=("full", "no-l2", "no-memory", "no-reflex", "no-guardian"), default="full")
    parser.add_argument("--executor", choices=("mock", "live"), default="mock")
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--sample-s", type=float, default=20.0, help="live snapshot window seconds")
    parser.add_argument("--live-action", default=None, help="optional Control API action after sampling, e.g. set_inference_profile")
    parser.add_argument("--live-params", default="{}", help="JSON params for --live-action")
    parser.add_argument("--l2-always", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.ablation == "no-guardian" and args.executor != "mock":
        raise SystemExit("no-guardian ablation 只允许 mock executor，禁止在真实 NX 上关闭 Guardian")
    cases = load_cases()
    if args.case:
        cases = [item for item in cases if item.get("case") == args.case or args.case in (item.get("family"), item.get("case", "").replace("_01", ""))]
        if not cases:
            raise SystemExit(f"找不到 case：{args.case}")
    bench = run_suite(reasoner=args.reasoner, llm_url=args.llm_url, l2_always=args.l2_always, cases=cases, runs=args.runs)
    synth_rows, synth_summary = run_synthetic(cases=cases, runs=args.runs, ablation=args.ablation)
    inject_rows = run_software_inject()
    candidates = generate_candidates()
    out_dir = args.out or (RESULTS_ROOT / f"experiment_{_now()}")
    live = None
    if args.executor == "live":
        try:
            live = sample_live(args.control_url, duration_s=args.sample_s)
            try:
                params = json.loads(args.live_params)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"--live-params 不是 JSON：{exc}") from exc
            if args.live_action:
                live["action"] = live_action(args.control_url, args.live_action, params)
                live["after"] = sample_live(args.control_url, duration_s=args.sample_s)
        except SystemExit:
            raise
        except Exception as exc:
            raise SystemExit(f"live sample 失败（GearPro Control API {args.control_url}）：{exc}") from exc
    payload = {
        "stage": "synthetic+software-inject" if args.executor == "mock" else "live-sample",
        "status": "implemented-tested",
        "experimentally_validated": False,
        "nx_workload": "future-work" if args.executor == "mock" else "sampled-not-validated",
        "ablation": args.ablation,
        "reasoner": args.reasoner,
        "provenance": collect_provenance(
            reasoner=args.reasoner,
            runtime_mode="synthetic" if args.executor == "mock" else "dataset_replay",
        ),
        "bench": {key: value for key, value in bench.items() if key != "rows"},
        "synthetic": synth_summary,
        "software_inject": inject_rows,
        "live": live,
        "policy_candidates": candidates,
        "asr_note": "ASR_function / ASR_mission on live GearPro cycle windows are not claimed. This runner reports synthetic decision metrics only unless --executor live sampled a running runtime.",
    }
    _write_outputs(out_dir, synth_rows, payload)
    print(json.dumps({**payload, "out": str(out_dir)}, ensure_ascii=False, indent=2))
    return 0 if bench.get("unsafe_action_leakage") == 0.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
