"""Fault injector calibration. No recovery actions. A3 is paused until qualified.

Compute-heavy GEMM/conv is disqualified: GPU util is not a V5_OVERLOAD proxy.
Next calibration is contention dimension (memory bandwidth, then SM occupancy).

Hard gates: triggerability, margin, sustainability, reversibility.
Selectivity is reported, not hard-gated, until calibration data exist.
Do not raise the 190 ms reset bar here; healthy envelope is measured separately.
Do not use jetson_clocks as the official A3 environment.
"""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import time

from edgemedic.a3 import overload_onset
from edgemedic.client import ControlClient
from edgemedic.gpu_pressure import (
    GpuContention,
    INJECTOR_TYPE,
    INJECTOR_VERSION,
    read_emc_mhz,
    read_gpu_clock_mhz,
    read_power_mode,
)
from edgemedic.policy import classify_fault
from edgemedic.provenance import FAULT_NONE, FAULT_REAL_RESOURCE_PRESSURE, collect_provenance, live_action, snapshot_telem, summarize_samples


RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
HOLD_S = 2.0
TARGET_FAULT_P95_MS = 220.0
ADMISSION_P95_MS = 190.0
ENVELOPE_P95_MS = (178.0, 186.0)

# Small contention matrix. Mixed only after memory and SM are measured separately.
SWEEP_CANDIDATES = (
    {"kind": "bandwidth", "bytes_mb": 256, "buffers": 3, "load_ms": 50, "idle_ms": 50, "matrix": 128, "streams": 4},
    {"kind": "bandwidth", "bytes_mb": 512, "buffers": 3, "load_ms": 80, "idle_ms": 20, "matrix": 128, "streams": 4},
    {"kind": "bandwidth", "bytes_mb": 768, "buffers": 4, "load_ms": 100, "idle_ms": 0, "matrix": 128, "streams": 4},
    {"kind": "sm", "bytes_mb": 64, "buffers": 2, "load_ms": 50, "idle_ms": 50, "matrix": 64, "streams": 2},
    {"kind": "sm", "bytes_mb": 64, "buffers": 2, "load_ms": 80, "idle_ms": 20, "matrix": 128, "streams": 4},
    {"kind": "sm", "bytes_mb": 64, "buffers": 2, "load_ms": 100, "idle_ms": 0, "matrix": 192, "streams": 8},
    {"kind": "mixed", "bytes_mb": 256, "buffers": 3, "load_ms": 80, "idle_ms": 20, "matrix": 128, "streams": 4},
    {"kind": "mixed", "bytes_mb": 512, "buffers": 4, "load_ms": 100, "idle_ms": 0, "matrix": 192, "streams": 8},
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


def qualify_cycle(healthy_p95, fault_p95, hold_s, recovered_p95, target_p95=TARGET_FAULT_P95_MS, hold_need=HOLD_S, admission_p95=ADMISSION_P95_MS):
    """Four gates: triggerability, margin, sustainability, reversibility.

    Reversibility uses the experiment admission gate (<190 ms), not the
    expected 178–186 ms envelope. A recovered 187–189 ms is jitter, not dirty state.
    """
    del healthy_p95
    triggerability = hold_s is not None and float(hold_s) >= float(hold_need)
    margin = fault_p95 is not None and float(fault_p95) >= float(target_p95)
    sustainability = triggerability and fault_p95 is not None and float(fault_p95) > 200.0
    reversible = recovered_p95 is not None and float(recovered_p95) < float(admission_p95)
    lo, hi = ENVELOPE_P95_MS
    in_expected_envelope = recovered_p95 is not None and lo <= float(recovered_p95) <= hi
    return {
        "triggerability": bool(triggerability),
        "margin": bool(margin),
        "sustainability": bool(sustainability),
        "reversible": bool(reversible),
        "in_expected_envelope": bool(in_expected_envelope),
        "below_fixed_190": reversible,
        "sustained": bool(triggerability),
        "pass": bool(triggerability and margin and sustainability and reversible),
    }


def selectivity_report(healthy, fault):
    """Observational V5-vs-locator split. Not a qualification hard gate."""
    healthy = healthy or {}
    fault = fault or {}
    healthy_loc = (healthy.get("locator") or {}).get("p95")
    fault_loc = (fault.get("locator") or {}).get("p95")
    healthy_v5 = healthy.get("v5_p95")
    fault_v5 = fault.get("v5_p95")
    loc_delta = None
    if healthy_loc is not None and fault_loc is not None:
        loc_delta = round(float(fault_loc) - float(healthy_loc), 3)
    v5_delta = None
    if healthy_v5 is not None and fault_v5 is not None:
        v5_delta = round(float(fault_v5) - float(healthy_v5), 3)
    return {
        "hard_gated": False,
        "v5_p95_healthy": healthy_v5,
        "v5_p95_fault": fault_v5,
        "v5_delta_ms": v5_delta,
        "locator_p95_healthy": healthy_loc,
        "locator_p95_fault": fault_loc,
        "locator_delta_ms": loc_delta,
        "valid_ratio_healthy": healthy.get("valid_ratio"),
        "valid_ratio_fault": fault.get("valid_ratio"),
        "note": "Selectivity thresholds TBD from calibration. Ideal: V5 worsens, locator stays near healthy, valid_ratio stays high.",
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
        telem["emc_mhz"] = read_emc_mhz()
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
    emc = [item.get("emc_mhz") for item in rows]
    utils = [item.get("gpu_util") for item in rows]
    temps = [item.get("temperature_c") for item in rows]
    powers = [item.get("power_w") for item in rows]
    events = [(item.get("t") or 0.0, bool(item.get("overload"))) for item in rows]
    hold = max_overload_hold_s(events)
    onset = overload_onset(events, hold_s=HOLD_S)
    t0 = rows[0].get("t") if rows else None
    summary["v5_p95"] = _percentile(v5, 95)
    summary["locator_p95"] = (summary.get("locator") or {}).get("p95")
    summary["gpu_clock_mhz_p50"] = _percentile(clocks, 50)
    summary["gpu_clock_mhz_max"] = None if not [c for c in clocks if c is not None] else max(c for c in clocks if c is not None)
    summary["emc_mhz_p50"] = _percentile(emc, 50)
    summary["gpu_util_p50"] = _percentile(utils, 50)
    summary["temperature_c_p50"] = _percentile(temps, 50)
    summary["power_w_p50"] = _percentile(powers, 50)
    summary["overload_hold_s"] = hold
    summary["sustained_onset"] = onset is not None
    summary["t_to_sustained_s"] = None if onset is None or t0 is None else round(float(onset) - float(t0), 3)
    summary["overload_fraction"] = None if not rows else round(sum(1 for item in rows if item.get("overload")) / len(rows), 4)
    return summary


def time_windows(rows, window_s=15.0):
    if not rows:
        return []
    t0 = float(rows[0].get("t") or 0.0)
    buckets = {}
    for item in rows:
        idx = int(max(0.0, float(item.get("t") or t0) - t0) // float(window_s))
        buckets.setdefault(idx, []).append(item)
    series = []
    for idx in sorted(buckets):
        chunk = buckets[idx]
        stats = _phase_stats(chunk)
        series.append(
            {
                "t0_s": round(idx * float(window_s), 1),
                "t1_s": round((idx + 1) * float(window_s), 1),
                "n": len(chunk),
                "v5_p50": (stats.get("scratch_v5") or {}).get("p50"),
                "v5_p95": stats.get("v5_p95"),
                "temperature_c": stats.get("temperature_c"),
                "power_w": stats.get("power_w"),
                "gpu_util": stats.get("gpu_util"),
                "gpu_clock_mhz_p50": stats.get("gpu_clock_mhz_p50"),
                "emc_mhz_p50": stats.get("emc_mhz_p50"),
                "locator_p95": stats.get("locator_p95"),
                "power_w_p50": stats.get("power_w_p50"),
                "overload_n": sum(1 for item in chunk if item.get("overload")),
            }
        )
    return series


def last_window(rows, seconds=60.0):
    if not rows:
        return None
    t1 = float(rows[-1].get("t") or 0.0)
    chunk = [item for item in rows if float(item.get("t") or 0.0) >= t1 - float(seconds)]
    return _phase_stats(chunk)


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
        "selectivity": selectivity_report(healthy, fault),
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
        streams=args.streams,
        buffers=args.buffers,
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
    parser.add_argument("--healthy-sample-s", type=float, default=18.0)
    parser.add_argument("--pressure-s", type=float, default=28.0)
    parser.add_argument("--settle-s", type=float, default=25.0)
    parser.add_argument("--sample-interval-s", type=float, default=0.25)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--target-v5-p95", type=float, default=TARGET_FAULT_P95_MS)
    parser.add_argument("--kind", choices=("bandwidth", "sm", "mixed", "gemm", "conv"), default="bandwidth")
    parser.add_argument("--matrix", type=int, default=128)
    parser.add_argument("--load-ms", type=float, default=100.0)
    parser.add_argument("--idle-ms", type=float, default=0.0)
    parser.add_argument("--bytes-mb", type=int, default=512)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--channels", type=int, default=16)
    parser.add_argument("--streams", type=int, default=4)
    parser.add_argument("--buffers", type=int, default=3)
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
            "windows_15s": time_windows(rows, 15.0),
            "last_60s": last_window(rows, 60.0),
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
        print(json.dumps({"mode": "healthy-drift", "out": str(out), "summary": payload["summary"], "windows_15s": payload["windows_15s"], "last_60s": {"v5_p95": (payload["last_60s"] or {}).get("v5_p95"), "temperature_c": (payload["last_60s"] or {}).get("temperature_c")}, "temp_bins": payload["temp_bins"]}, ensure_ascii=False, indent=2))
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
                row["injector_config"] = pressure.config()
                row["injector_hash"] = pressure.hash()
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
            "fault_injector_type": INJECTOR_TYPE,
            "fault_injector_version": INJECTOR_VERSION,
            "power_mode": read_power_mode(),
            "target_v5_p95_ms": args.target_v5_p95,
            "hold_s": HOLD_S,
            "candidates": results,
            "best": None if not ranked else ranked[0].get("candidate"),
            "note": (
                "Compute-heavy GEMM/conv is disqualified. Sweep is not qualification. "
                "GPU util is not a V5_OVERLOAD proxy. Run --mode qualify only after a candidate "
                "passes triggerability+margin+sustainability+reversibility. Selectivity is reported, not gated. "
                "Do not enable jetson_clocks for the official A3 environment."
            ),
            "provenance": collect_provenance(
                reasoner="none",
                runtime_mode="dataset_replay",
                snapshot=client.get_state(),
                fault_mode=FAULT_REAL_RESOURCE_PRESSURE,
                experiment_config={
                    "kind": "injector_sweep",
                    "fault_injector_type": INJECTOR_TYPE,
                    "fault_injector_version": INJECTOR_VERSION,
                    "sweep_matrix": list(SWEEP_CANDIDATES),
                },
                replay_pack_dir=args.replay_pack,
            ),
        }
        _write(out, payload)
        brief = [
            {
                "candidate": row.get("candidate"),
                "pass": row.get("pass"),
                "fault_v5_p95": (row.get("fault") or {}).get("v5_p95"),
                "locator_p95_fault": (row.get("fault") or {}).get("locator_p95"),
                "hold_s": (row.get("fault") or {}).get("overload_hold_s"),
                "healthy_v5_p95": (row.get("healthy") or {}).get("v5_p95"),
                "recovered_v5_p95": (row.get("recovered") or {}).get("v5_p95"),
                "gpu_clock_fault": (row.get("fault") or {}).get("gpu_clock_mhz_p50"),
                "emc_mhz_fault": (row.get("fault") or {}).get("emc_mhz_p50"),
                "power_w_fault": (row.get("fault") or {}).get("power_w_p50"),
                "temperature_c_fault": (row.get("fault") or {}).get("temperature_c_p50"),
                "selectivity": row.get("selectivity"),
            }
            for row in results
        ]
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
