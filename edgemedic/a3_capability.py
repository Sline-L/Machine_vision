"""Severity response: FULL vs SPARSE under multi_bandwidth (no recovery).

Steady-state characterization only. Does not compute ASR/MTTR.
"""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import json
import time

from edgemedic.client import ControlClient
from edgemedic.gpu_pressure import INJECTOR_TYPE, INJECTOR_VERSION, read_emc_mhz, read_gpu_clock_mhz, read_power_mode
from edgemedic.multi_pressure import MultiGpuContention
from edgemedic.provenance import FAULT_NONE, FAULT_REAL_RESOURCE_PRESSURE, collect_provenance, live_action, snapshot_telem


RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
ADMISSION_P95_MS = 190.0

SEVERITY_GRID = (
    {"id": "S0", "label": "healthy", "load_ms": 0, "idle_ms": 100, "injector_on": False},
    {"id": "S1", "label": "light", "load_ms": 40, "idle_ms": 60, "injector_on": True},
    {"id": "S2", "label": "medium_light", "load_ms": 60, "idle_ms": 40, "injector_on": True},
    {"id": "S3", "label": "medium", "load_ms": 75, "idle_ms": 25, "injector_on": True},
    {"id": "S4", "label": "medium_high", "load_ms": 90, "idle_ms": 10, "injector_on": True},
    {"id": "S5", "label": "severe", "load_ms": 100, "idle_ms": 0, "injector_on": True},
)

SEVERITY_GRID_CHECK = (
    {"id": "S0", "label": "healthy", "load_ms": 0, "idle_ms": 100, "injector_on": False},
    {"id": "S1", "label": "light", "load_ms": 40, "idle_ms": 60, "injector_on": True},
    {"id": "S5", "label": "severe", "load_ms": 100, "idle_ms": 0, "injector_on": True},
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


def _mean(values):
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


def _set_profile(url, profile, warmup_s):
    live_action(url, "set_locator_profile", {"profile": "pt_safe"}, source="reflex")
    live_action(url, "set_inference_profile", {"profile": profile}, source="reflex")
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
        rows.append(telem)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(float(interval), remaining))
    return rows


def _summarize(rows):
    if not rows:
        return {}
    t0 = float(rows[0]["t"])
    t1 = float(rows[-1]["t"])
    wall = max(1e-6, t1 - t0)
    v5 = [r.get("v5_latency_ms") for r in rows if r.get("v5_latency_ms") is not None]
    loc = [r.get("locator_latency_ms") for r in rows if r.get("locator_latency_ms") is not None]
    utils = [r.get("utility") for r in rows]
    clocks = [r.get("gpu_clock_mhz") for r in rows]
    emc = [r.get("emc_mhz") for r in rows]
    gpu_u = [r.get("gpu_util") for r in rows]
    temps = [r.get("temperature_c") for r in rows]
    powers = [r.get("power_w") for r in rows]
    valid = [r for r in rows if r.get("output_valid")]
    counts = [r.get("inspection_count") for r in rows if r.get("inspection_count") is not None]
    inspect_rate = None
    if len(counts) >= 2:
        inspect_rate = round((float(counts[-1]) - float(counts[0])) / wall, 4)
    intervals = [r.get("inference_interval_s") for r in rows if r.get("inference_interval_s") is not None]
    return {
        "n_samples": len(rows),
        "wall_s": round(wall, 3),
        "v5_p50": _percentile(v5, 50),
        "v5_p95": _percentile(v5, 95),
        "locator_p50": _percentile(loc, 50),
        "locator_p95": _percentile(loc, 95),
        "valid_ratio": None if not rows else round(len(valid) / len(rows), 4),
        "utility_mean": _mean(utils),
        "cycle_rate_hz": inspect_rate,
        "sample_rate_hz": round(len(rows) / wall, 4),
        "v5_obs_rate_hz": round(len(v5) / wall, 4),
        "inspection_count_delta": None if len(counts) < 2 else int(counts[-1]) - int(counts[0]),
        "inference_interval_s": None if not intervals else intervals[-1],
        "gpu_clock_mhz_p50": _percentile(clocks, 50),
        "gpu_clock_mhz_max": None if not [c for c in clocks if c is not None] else max(c for c in clocks if c is not None),
        "emc_mhz_p50": _percentile(emc, 50),
        "gpu_util_p50": _percentile(gpu_u, 50),
        "temperature_c_p50": _percentile(temps, 50),
        "power_w_p50": _percentile(powers, 50),
        "profile": rows[-1].get("profile"),
        "locator_backend": rows[-1].get("locator_backend"),
        "actual_fps": rows[-1].get("actual_fps"),
    }


def _admission_ok(stats):
    v5 = stats.get("v5_p95")
    return v5 is not None and float(v5) < float(ADMISSION_P95_MS)


def _pressure(args, severity):
    return MultiGpuContention(
        replicas=args.replicas,
        kind="bandwidth",
        bytes_mb=args.bytes_mb,
        buffers=args.buffers,
        streams=args.streams,
        matrix=args.matrix,
        load_ms=severity["load_ms"],
        idle_ms=severity["idle_ms"],
    )


def _interleaved(severities):
    """Alternate which profile goes first to reduce thermal bias."""
    schedule = []
    for index, sev in enumerate(severities):
        if index % 2 == 0:
            schedule.append((sev, "FULL"))
            schedule.append((sev, "SPARSE"))
        else:
            schedule.append((sev, "SPARSE"))
            schedule.append((sev, "FULL"))
    return schedule


def run_point(client, url, args, severity, profile):
    pressure = _pressure(args, severity)
    pressure.stop()
    time.sleep(max(0.0, float(args.settle_s)))
    _set_profile(url, profile, args.warmup_s)
    admit_rows = _sample(client, args.admission_s, args.sample_interval_s)
    admit = _summarize(admit_rows)
    if not _admission_ok(admit):
        return {
            "aborted": True,
            "abort_reason": f"admission fail V5 p95={admit.get('v5_p95')}",
            "severity": severity,
            "profile": profile,
            "admission": admit,
        }
    started = None
    if severity.get("injector_on"):
        started = pressure.start()
        if not pressure.alive():
            pressure.stop()
            return {
                "aborted": True,
                "abort_reason": "injector died",
                "severity": severity,
                "profile": profile,
                "admission": admit,
            }
    steady_rows = _sample(client, args.sample_s, args.sample_interval_s)
    alive = True if not severity.get("injector_on") else pressure.alive()
    pressure.stop()
    time.sleep(max(0.0, float(args.settle_s)))
    settle_rows = _sample(client, args.admission_s, args.sample_interval_s)
    settle = _summarize(settle_rows)
    return {
        "aborted": False,
        "severity": severity,
        "profile": profile,
        "admission": admit,
        "steady": _summarize(steady_rows),
        "settle": settle,
        "settle_admission_ok": _admission_ok(settle),
        "injector": started,
        "injector_alive": alive,
        "power_mode": read_power_mode(),
    }


def _write_table(out, rows):
    path = out / "response_table.csv"
    fields = [
        "severity_id",
        "severity_label",
        "load_ms",
        "idle_ms",
        "profile",
        "v5_p50",
        "v5_p95",
        "locator_p50",
        "locator_p95",
        "valid_ratio",
        "cycle_rate_hz",
        "v5_obs_rate_hz",
        "utility_mean",
        "gpu_clock_mhz_p50",
        "emc_mhz_p50",
        "gpu_util_p50",
        "power_w_p50",
        "temperature_c_p50",
        "settle_v5_p95",
        "aborted",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            sev = row.get("severity") or {}
            steady = row.get("steady") or {}
            settle = row.get("settle") or {}
            writer.writerow(
                {
                    "severity_id": sev.get("id"),
                    "severity_label": sev.get("label"),
                    "load_ms": sev.get("load_ms"),
                    "idle_ms": sev.get("idle_ms"),
                    "profile": row.get("profile"),
                    "v5_p50": steady.get("v5_p50"),
                    "v5_p95": steady.get("v5_p95"),
                    "locator_p50": steady.get("locator_p50"),
                    "locator_p95": steady.get("locator_p95"),
                    "valid_ratio": steady.get("valid_ratio"),
                    "cycle_rate_hz": steady.get("cycle_rate_hz"),
                    "v5_obs_rate_hz": steady.get("v5_obs_rate_hz"),
                    "utility_mean": steady.get("utility_mean"),
                    "gpu_clock_mhz_p50": steady.get("gpu_clock_mhz_p50"),
                    "emc_mhz_p50": steady.get("emc_mhz_p50"),
                    "gpu_util_p50": steady.get("gpu_util_p50"),
                    "power_w_p50": steady.get("power_w_p50"),
                    "temperature_c_p50": steady.get("temperature_c_p50"),
                    "settle_v5_p95": settle.get("v5_p95"),
                    "aborted": row.get("aborted"),
                }
            )
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="A3 capability severity response (no recovery)")
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--replay-pack", type=Path, default=Path("tests/replay"))
    parser.add_argument("--replicas", type=int, default=3)
    parser.add_argument("--bytes-mb", type=int, default=512)
    parser.add_argument("--buffers", type=int, default=3)
    parser.add_argument("--streams", type=int, default=4)
    parser.add_argument("--matrix", type=int, default=128)
    parser.add_argument("--warmup-s", type=float, default=12.0)
    parser.add_argument("--admission-s", type=float, default=12.0)
    parser.add_argument("--sample-s", type=float, default=40.0)
    parser.add_argument("--settle-s", type=float, default=20.0)
    parser.add_argument("--sample-interval-s", type=float, default=0.25)
    parser.add_argument("--grid", choices=("full", "check"), default="full")
    parser.add_argument("--repeats", type=int, default=1, help="repeat each severity×profile block")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    client = ControlClient(args.control_url, timeout=5.0)
    url = args.control_url
    out = args.out or (RESULTS_ROOT / "a3_capability" / f"{_stamp()}_severity_response")
    out.mkdir(parents=True, exist_ok=True)
    grid = SEVERITY_GRID_CHECK if args.grid == "check" else SEVERITY_GRID
    schedule = []
    for _rep in range(max(1, int(args.repeats))):
        schedule.extend(_interleaved(grid))
    results = []
    try:
        for index, (severity, profile) in enumerate(schedule):
            row = run_point(client, url, args, severity, profile)
            row["repeat"] = index
            results.append(row)
            (out / f"{index:02d}_{severity['id']}_{profile}.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    finally:
        try:
            _set_profile(url, "FULL", 2.0)
        except Exception:
            pass
    table = _write_table(out, results)
    base_cfg = {
        "kind": "multi_bandwidth",
        "replicas": args.replicas,
        "bytes_mb": args.bytes_mb,
        "buffers": args.buffers,
        "streams": args.streams,
        "matrix": args.matrix,
        "severity_grid": list(grid),
    }
    pressure0 = _pressure(args, grid[-1])
    payload = {
        "stage": "a3-capability-severity-response",
        "a3_claim": False,
        "experimentally_validated": False,
        "fault_injector_type": INJECTOR_TYPE,
        "fault_injector_version": INJECTOR_VERSION,
        "injector_base": base_cfg,
        "injector_hash_severe": pressure0.hash(),
        "power_mode": read_power_mode(),
        "schedule": [{"severity": s["id"], "profile": p} for s, p in schedule],
        "points": results,
        "table_csv": str(table),
        "provenance": collect_provenance(
            reasoner="none",
            runtime_mode="dataset_replay",
            snapshot=client.get_state(),
            fault_mode=FAULT_REAL_RESOURCE_PRESSURE,
            experiment_config={
                "kind": "a3_capability_severity_response",
                "grid": args.grid,
                "repeats": args.repeats,
                "fault_injector_type": INJECTOR_TYPE,
                "fault_injector_version": INJECTOR_VERSION,
                "injector_base": base_cfg,
                "sample_s": args.sample_s,
            },
            replay_pack_dir=args.replay_pack,
        ),
        "note": (
            "Steady-state FULL vs SPARSE under multi_bandwidth duty-cycle severity. "
            "cycle_rate_hz counts snapshot latency changes (last-result telemetry). "
            "Not ASR/MTTR. Do not retune Mission thresholds from this file."
        ),
    }
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = []
    for row in results:
        sev = row.get("severity") or {}
        steady = row.get("steady") or {}
        brief.append(
            {
                "severity": sev.get("id"),
                "profile": row.get("profile"),
                "pass_admission": not row.get("aborted"),
                "v5_p95": steady.get("v5_p95"),
                "cycle_rate_hz": steady.get("cycle_rate_hz"),
                "utility_mean": steady.get("utility_mean"),
                "locator_p95": steady.get("locator_p95"),
            }
        )
    print(json.dumps({"out": str(out), "rows": brief}, ensure_ascii=False, indent=2))
    return 0 if not any(r.get("aborted") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
