"""Fault injector calibration. No recovery actions. A3 is paused until qualified.

Hard gates: repeatable (5 consecutive), sustained (>=2 s overload with V5
margin), reversible (post-settle returns to that cycle's healthy band).
Do not raise the 190 ms reset bar here; healthy envelope is measured separately.
"""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import time

from edgemedic.a3 import overload_onset
from edgemedic.client import ControlClient
from edgemedic.gpu_pressure import GpuContention, INJECTOR_TYPE, INJECTOR_VERSION, read_gpu_clock_mhz, read_power_mode
from edgemedic.policy import classify_fault
from edgemedic.provenance import FAULT_NONE, FAULT_REAL_RESOURCE_PRESSURE, collect_provenance, live_action, snapshot_telem, summarize_samples


RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
HOLD_S = 2.0
TARGET_FAULT_P95_MS = 230.0
REVERSIBLE_SLACK_MS = 8.0

SWEEP_CANDIDATES = (
    {"kind": "gemm", "matrix": 1024, "load_ms": 50, "idle_ms": 50, "bytes_mb": 256},
    {"kind": "gemm", "matrix": 1024, "load_ms": 80, "idle_ms": 20, "bytes_mb": 256},
    {"kind": "gemm", "matrix": 1024, "load_ms": 100, "idle_ms": 0, "bytes_mb": 256},
    {"kind": "gemm", "matrix": 2048, "load_ms": 80, "idle_ms": 20, "bytes_mb": 256},
    {"kind": "bandwidth", "matrix": 1024, "load_ms": 80, "idle_ms": 20, "bytes_mb": 256},
    {"kind": "bandwidth", "matrix": 1024, "load_ms": 100, "idle_ms": 0, "bytes_mb": 512},
    {"kind": "mixed", "matrix": 1024, "load_ms": 80, "idle_ms": 20, "bytes_mb": 256},
)


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _percentile(values, pct):
    ordered = sorted(float(item) for item in values if item is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return round(ordered[low] * (1.0 - frac) + ordered[high] * frac, 3)


def max_overload_hold_s(events):
    best = 0.0
    start = None
    last = None
    for stamp, overloaded in events:
        stamp = float(stamp)
        if overloaded:
            if start is None:
                start = stamp
            last = stamp
            best = max(best, last - start)
        else:
            start = None
            last = None
    return round(best, 3)


def qualify_cycle(healthy_p95, fault_p95, hold_s, recovered_p95, target_p95=TARGET_FAULT_P95_MS, hold_need=HOLD_S, slack_ms=REVERSIBLE_SLACK_MS):
    sustained = hold_s is not None and float(hold_s) >= float(hold_need)
    margin = fault_p95 is not None and float(fault_p95) >= float(target_p95)
    reversible = (
        recovered_p95 is not None
        and healthy_p95 is not None
        and float(recovered_p95) <= float(healthy_p95) + float(slack_ms)
    )
    return {
        "sustained": bool(sustained),
        "margin": bool(margin),
        "reversible": bool(reversible),
        "below_fixed_190": recovered_p95 is not None and float(recovered_p95) <= 190.0,
        "pass": bool(sustained and margin and reversible),
    }


def qualify_verdict(cycles, repeats=5):
    rows = list(cycles or [])
    if len(rows) < int(repeats):
        return {
            "fault_injector_qualified": False,
            "repeatable": False,
            "reason": f"need {repeats} consecutive cycles, got {len(rows)}",
            "n": len(rows),
        }
    window = rows[-int(repeats) :]
    repeatable = all(item.get("pass") for item in window)
    return {
        "fault_injector_qualified": bool(repeatable),
        "repeatable": bool(repeatable),
        "sustained": all(item.get("sustained") for item in window),
        "reversible": all(item.get("reversible") for item in window),
        "n": len(window),
        "reason": None if repeatable else "consecutive qualification window failed",
    }


def load_qualification(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def a3_blocked_reason(qual):
    if not qual:
        return "no injector qualification file"
    if not qual.get("fault_injector_qualified"):
        return "fault_injector_qualified is not true"
    return None


def _reset_full_pt(url, warmup_s):
    live_action(url, "set_locator_profile", {"profile": "pt_safe"}, source="reflex")
    live_action(url, "set_inference_profile", {"profile": "FULL"}, source="reflex")
    time.sleep(max(0.0, float(warmup_s)))


def _sample(client, duration_s, interval=0.25):
    rows = []
    deadline = time.monotonic() + max(0.1, float(duration_s))
    while time.monotonic() <= deadline:
        snapshot = client.get_state()
        telem = snapshot_telem(snapshot)
        telem["t"] = time.monotonic()
        telem["gpu_clock_mhz"] = read_gpu_clock_mhz()
        telem["overload"] = classify_fault(snapshot) == "V5_OVERLOAD"
        rows.append(telem)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(float(interval), remaining))
    return rows


def _phase_stats(rows):
    summary = summarize_samples(rows)
    v5 = [item.get("v5_latency_ms") for item in rows]
    clocks = [item.get("gpu_clock_mhz") for item in rows]
    events = [(item.get("t") or 0.0, bool(item.get("overload"))) for item in rows]
    hold = max_overload_hold_s(events)
    onset = overload_onset(events, hold_s=HOLD_S)
    summary["v5_p95"] = _percentile(v5, 95)
    summary["gpu_clock_mhz_p50"] = _percentile(clocks, 50)
    summary["gpu_clock_mhz_max"] = None if not [c for c in clocks if c is not None] else max(c for c in clocks if c is not None)
    summary["overload_hold_s"] = hold
    summary["sustained_onset"] = onset is not None
    summary["overload_fraction"] = None if not rows else round(sum(1 for item in rows if item.get("overload")) / len(rows), 4)
    return summary


def run_cycle(client, url, pressure, args):
    pressure.stop()
    time.sleep(max(0.0, float(args.settle_s)))
    _reset_full_pt(url, args.warmup_s)
    healthy_rows = _sample(client, args.healthy_sample_s, args.sample_interval_s)
    healthy = _phase_stats(healthy_rows)
    started = pressure.start()
    if not pressure.alive():
        pressure.stop()
        return {"aborted": True, "abort_reason": "injector died", "healthy": healthy}
    fault_rows = _sample(client, args.pressure_s, args.sample_interval_s)
    injector_alive = pressure.alive()
    pressure.stop()
    time.sleep(max(0.0, float(args.settle_s)))
    recovered_rows = _sample(client, args.healthy_sample_s, args.sample_interval_s)
    fault = _phase_stats(fault_rows)
    recovered = _phase_stats(recovered_rows)
    gates = qualify_cycle(healthy.get("v5_p95"), fault.get("v5_p95"), fault.get("overload_hold_s"), recovered.get("v5_p95"), target_p95=args.target_v5_p95)
    return {
        "aborted": False,
        "healthy": healthy,
        "fault": fault,
        "recovered": recovered,
        "injector": started,
        "injector_alive": injector_alive,
        "power_mode": read_power_mode(),
        **gates,
    }


def _pressure_from_args(args):
    return GpuContention(
        kind=args.kind,
        matrix=args.matrix,
        load_ms=args.load_ms,
        idle_ms=args.idle_ms,
        bytes_mb=args.bytes_mb,
        size=args.size,
        batch=args.batch,
        channels=args.channels,
        nice=args.nice,
    )


def _write(out, payload):
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fault injector calibration (no recovery)")
    parser.add_argument("--mode", choices=("sweep", "qualify", "healthy-drift"), required=True)
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--replay-pack", type=Path, default=Path("tests/replay"))
    parser.add_argument("--warmup-s", type=float, default=15.0)
    parser.add_argument("--healthy-sample-s", type=float, default=15.0)
    parser.add_argument("--pressure-s", type=float, default=20.0)
    parser.add_argument("--settle-s", type=float, default=15.0)
    parser.add_argument("--sample-interval-s", type=float, default=0.25)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--target-v5-p95", type=float, default=TARGET_FAULT_P95_MS)
    parser.add_argument("--kind", choices=("gemm", "bandwidth", "mixed", "conv"), default="gemm")
    parser.add_argument("--matrix", type=int, default=1024)
    parser.add_argument("--load-ms", type=float, default=80.0)
    parser.add_argument("--idle-ms", type=float, default=20.0)
    parser.add_argument("--bytes-mb", type=int, default=256)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--channels", type=int, default=16)
    parser.add_argument("--nice", type=int, default=None)
    parser.add_argument("--duration-s", type=float, default=180.0, help="healthy-drift duration")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    client = ControlClient(args.control_url, timeout=5.0)
    snapshot = client.get_state()
    url = args.control_url
    out = args.out or (RESULTS_ROOT / f"injector_qual_{args.mode}_{_stamp()}")

    if args.mode == "healthy-drift":
        _reset_full_pt(url, args.warmup_s)
        rows = _sample(client, args.duration_s, args.sample_interval_s)
        bins = {"lt60": [], "60_65": [], "65_70": [], "ge70": [], "unknown": []}
        for item in rows:
            temp = item.get("temperature_c")
            v5 = item.get("v5_latency_ms")
            if v5 is None:
                continue
            if temp is None:
                bins["unknown"].append(v5)
            elif temp < 60:
                bins["lt60"].append(v5)
            elif temp < 65:
                bins["60_65"].append(v5)
            elif temp < 70:
                bins["65_70"].append(v5)
            else:
                bins["ge70"].append(v5)
        payload = {
            "stage": "injector-healthy-drift",
            "fault_injector_qualified": False,
            "a3_claim": False,
            "summary": _phase_stats(rows),
            "temp_bins": {
                key: {"n": len(vals), "v5_p50": _percentile(vals, 50), "v5_p95": _percentile(vals, 95)}
                for key, vals in bins.items()
            },
            "note": "Do not raise the 190 ms A3 reset bar from this file until the envelope is reviewed.",
            "provenance": collect_provenance(
                reasoner="none",
                runtime_mode="dataset_replay",
                snapshot=snapshot,
                fault_mode=FAULT_NONE,
                experiment_config={"kind": "healthy_drift", "duration_s": args.duration_s},
                replay_pack_dir=args.replay_pack,
            ),
        }
        _write(out, payload)
        print(json.dumps({"mode": "healthy-drift", "out": str(out), "summary": payload["summary"], "temp_bins": payload["temp_bins"]}, ensure_ascii=False, indent=2))
        return 0

    if args.mode == "sweep":
        results = []
        try:
            for spec in SWEEP_CANDIDATES:
                pressure = GpuContention(**spec)
                cycle_args = argparse.Namespace(**vars(args))
                for key, value in spec.items():
                    setattr(cycle_args, key, value)
                row = run_cycle(client, url, pressure, cycle_args)
                row["candidate"] = spec
                results.append(row)
        finally:
            pass
        ranked = sorted(
            [row for row in results if not row.get("aborted")],
            key=lambda item: (
                0 if item.get("pass") else 1,
                -(item.get("fault") or {}).get("v5_p95") or 0.0,
            ),
        )
        payload = {
            "stage": "injector-sweep",
            "fault_injector_qualified": False,
            "a3_claim": False,
            "target_v5_p95_ms": args.target_v5_p95,
            "hold_s": HOLD_S,
            "candidates": results,
            "best": None if not ranked else ranked[0].get("candidate"),
            "note": "Sweep is not qualification. Run --mode qualify with 5 consecutive cycles on one candidate.",
            "provenance": collect_provenance(
                reasoner="none",
                runtime_mode="dataset_replay",
                snapshot=client.get_state(),
                fault_mode=FAULT_REAL_RESOURCE_PRESSURE,
                experiment_config={"kind": "injector_sweep", "candidates": list(SWEEP_CANDIDATES)},
                replay_pack_dir=args.replay_pack,
            ),
        }
        _write(out, payload)
        brief = [{ "candidate": row.get("candidate"), "pass": row.get("pass"), "fault_v5_p95": (row.get("fault") or {}).get("v5_p95"), "hold_s": (row.get("fault") or {}).get("overload_hold_s"), "healthy_v5_p95": (row.get("healthy") or {}).get("v5_p95"), "recovered_v5_p95": (row.get("recovered") or {}).get("v5_p95"), "gpu_clock_fault": (row.get("fault") or {}).get("gpu_clock_mhz_p50")} for row in results]
        print(json.dumps({"mode": "sweep", "out": str(out), "rows": brief, "best": payload["best"]}, ensure_ascii=False, indent=2))
        return 0

    pressure = _pressure_from_args(args)
    cycles = []
    try:
        for index in range(max(1, int(args.repeats))):
            row = run_cycle(client, url, pressure, args)
            row["repeat"] = index
            cycles.append(row)
            if row.get("aborted"):
                break
    finally:
        pressure.stop()
        try:
            _reset_full_pt(url, 2.0)
        except Exception:
            pass
    gates = [qualify_cycle((c.get("healthy") or {}).get("v5_p95"), (c.get("fault") or {}).get("v5_p95"), (c.get("fault") or {}).get("overload_hold_s"), (c.get("recovered") or {}).get("v5_p95"), target_p95=args.target_v5_p95) for c in cycles if not c.get("aborted")]
    verdict = qualify_verdict(gates, repeats=args.repeats)
    payload = {
        "stage": "injector-qualify",
        "fault_injector_qualified": verdict["fault_injector_qualified"],
        "a3_claim": False,
        "verdict": verdict,
        "target_v5_p95_ms": args.target_v5_p95,
        "hold_s": HOLD_S,
        "cycles": cycles,
        "injector": pressure.config(),
        "injector_hash": pressure.hash(),
        "fault_injector_type": INJECTOR_TYPE,
        "fault_injector_version": INJECTOR_VERSION,
        "power_mode": read_power_mode(),
        "provenance": collect_provenance(
            reasoner="none",
            runtime_mode="dataset_replay",
            snapshot=client.get_state(),
            fault_mode=FAULT_REAL_RESOURCE_PRESSURE,
            experiment_config={
                "kind": "injector_qualify",
                "repeats": args.repeats,
                "fault_injector_type": INJECTOR_TYPE,
                "fault_injector_version": INJECTOR_VERSION,
                "fault_injector_config": pressure.config(),
                "fault_injector_hash": pressure.hash(),
                "target_v5_p95_ms": args.target_v5_p95,
            },
            replay_pack_dir=args.replay_pack,
        ),
        "note": "A3 remains paused unless fault_injector_qualified is true. Do not treat this file as ASR/MTTR.",
    }
    _write(out, payload)
    latest = RESULTS_ROOT / "injector_qual"
    _write(latest, payload)
    print(json.dumps({"mode": "qualify", "out": str(out), "verdict": verdict, "cycles": [{"repeat": c.get("repeat"), "pass": c.get("pass"), "fault_v5_p95": (c.get("fault") or {}).get("v5_p95"), "hold_s": (c.get("fault") or {}).get("overload_hold_s")} for c in cycles]}, ensure_ascii=False, indent=2))
    return 0 if verdict.get("fault_injector_qualified") else 2


if __name__ == "__main__":
    raise SystemExit(main())
