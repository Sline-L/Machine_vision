"""Secondary B feasibility: service pressure under LatestFrame + interval.

Does NOT change SPARSE interval/Q_D or Mission latency gates.
Development / pilot data only until a controlled protocol is frozen.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from edgemedic.secondary_b_metrics import account_demand_opportunities, summarize_ages
from gp.config import PROJECT_ROOT, AppConfig
from gp.frames import LatestFrame
from gp.models import TwoStageInspector
from gp.replay import load_replay_pack

try:
    from edgemedic.gpu_pressure import read_emc_mhz, read_gpu_clock_mhz, read_power_mode
    from edgemedic.multi_pressure import MultiGpuContention
except Exception:  # pragma: no cover
    read_emc_mhz = read_gpu_clock_mhz = read_power_mode = None
    MultiGpuContention = None


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _mission_utility(profile: str, valid: bool):
    # Healthy Q_L=Q_S=1; Q_D ceiling FULL=1.0 SPARSE=0.9
    ceiling = 0.90 if profile == "SPARSE" else 1.00
    if not valid:
        return round(0.3 * 1.0 + 0.5 * 0.0 + 0.2 * 1.0, 4)
    return round(0.3 * 1.0 + 0.5 * ceiling + 0.2 * 1.0, 4)


class FramePublisher(threading.Thread):
    """Publish replay frames at a fixed arrival rate into LatestFrame."""

    def __init__(self, store: LatestFrame, frames, hz: float, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.store = store
        self.frames = list(frames)
        self.hz = float(hz)
        self.stop_event = stop_event
        self.published = 0

    def run(self):
        if not self.frames:
            return
        period = 1.0 / max(0.1, self.hz)
        idx = 0
        while not self.stop_event.is_set():
            path = self.frames[idx % len(self.frames)]
            idx += 1
            image = cv2.imread(str(path))
            if image is not None:
                self.store.publish(image)
                self.published += 1
            if self.stop_event.wait(period):
                break


class DemandClock(threading.Thread):
    """Profile-independent external demand opportunity clock."""

    def __init__(self, hz: float, stop_event: threading.Event, sink: list):
        super().__init__(daemon=True)
        self.hz = float(hz)
        self.stop_event = stop_event
        self.sink = sink

    def run(self):
        period = 1.0 / max(0.1, self.hz)
        while not self.stop_event.is_set():
            self.sink.append(time.monotonic())
            if self.stop_event.wait(period):
                break


def run_worker_loop(
    store: LatestFrame,
    inspector: TwoStageInspector,
    interval_s: float,
    duration_s: float,
    stop_extra: threading.Event,
):
    events = []
    ages = []
    lags = []
    walls = []
    v5 = []
    loc = []
    last_seq = -1
    deadline = time.monotonic() + float(duration_s)
    busy = 0.0
    t0 = time.monotonic()
    while time.monotonic() < deadline and not stop_extra.is_set():
        packet = store.read()
        if packet.frame is not None and packet.sequence != last_seq:
            last_seq = packet.sequence
            started = time.monotonic()
            result = inspector.inspect(packet.frame)
            ended = time.monotonic()
            latest = store.read()
            wall = (ended - started) * 1000.0
            busy += ended - started
            age = None if packet.published_at is None else (ended - packet.published_at) * 1000.0
            lag = latest.sequence - packet.sequence
            valid = bool(result.has_gear)
            events.append(
                {
                    "start": started,
                    "end": ended,
                    "valid": valid,
                    "source_seq": packet.sequence,
                    "latest_seq": latest.sequence,
                    "age_ms": age,
                    "frame_lag": lag,
                    "wall_ms": wall,
                    "v5_ms": result.scratch_latency_ms,
                    "locator_ms": result.locator_latency_ms,
                }
            )
            if age is not None:
                ages.append(age)
            lags.append(lag)
            walls.append(wall)
            if result.scratch_latency_ms is not None:
                v5.append(result.scratch_latency_ms)
            if result.locator_latency_ms is not None:
                loc.append(result.locator_latency_ms)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        stop_extra.wait(min(float(interval_s), remaining))
    wall_total = max(1e-6, time.monotonic() - t0)
    return {
        "events": events,
        "ages": ages,
        "lags": lags,
        "walls": walls,
        "v5": v5,
        "locator": loc,
        "n_completed": len(events),
        "n_valid": sum(1 for e in events if e["valid"]),
        "lambda_served": len(events) / wall_total,
        "worker_busy_fraction": busy / wall_total,
        "wall_s": wall_total,
    }


def phase_resources():
    out = {"gpu_clock_mhz": None, "emc_mhz": None, "power_mode": None}
    if read_gpu_clock_mhz:
        out["gpu_clock_mhz"] = read_gpu_clock_mhz()
    if read_emc_mhz:
        out["emc_mhz"] = read_emc_mhz()
    if read_power_mode:
        out["power_mode"] = read_power_mode()
    return out


def run_arm(
    inspector,
    frames,
    profile: str,
    interval_s: float,
    arrival_hz: float,
    demand_hz: float,
    duration_s: float,
    pressure=None,
):
    store = LatestFrame()
    stop = threading.Event()
    demand_times = []
    publisher = FramePublisher(store, frames, arrival_hz, stop)
    demand = DemandClock(demand_hz, stop, demand_times)
    # Prime one frame
    img = cv2.imread(str(frames[0]))
    if img is not None:
        store.publish(img)
    publisher.start()
    demand.start()
    if pressure is not None:
        pressure.start()
    time.sleep(0.5)
    worker = run_worker_loop(store, inspector, interval_s, duration_s, stop)
    stop.set()
    publisher.join(timeout=2.0)
    demand.join(timeout=2.0)
    if pressure is not None:
        pressure.stop()
    accounting = account_demand_opportunities(demand_times, worker["events"], interval_s)
    valid_ratio = (
        worker["n_valid"] / worker["n_completed"] if worker["n_completed"] else None
    )
    return {
        "profile": profile,
        "interval_s": interval_s,
        "arrival_hz": arrival_hz,
        "demand_hz": demand_hz,
        "duration_s": duration_s,
        "frames_published": publisher.published,
        "InspectionAge": summarize_ages(worker["ages"]),
        "FrameLag": summarize_ages(worker["lags"]),
        "inspect_wall_ms": summarize_ages(worker["walls"]),
        "v5_ms": summarize_ages(worker["v5"]),
        "locator_ms": summarize_ages(worker["locator"]),
        "lambda_served": round(worker["lambda_served"], 4),
        "worker_busy_fraction": round(worker["worker_busy_fraction"], 4),
        "valid_ratio": None if valid_ratio is None else round(valid_ratio, 4),
        "MissionUtility_nominal": _mission_utility(profile, True),
        "accounting": accounting,
        "resources_end": phase_resources(),
        "n_completed": worker["n_completed"],
        "claim": "DEVELOPMENT / PILOT ONLY",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-pack", type=Path, default=PROJECT_ROOT / "tests" / "replay")
    parser.add_argument("--locator", type=Path, default=PROJECT_ROOT / "model" / "model1.pt")
    parser.add_argument(
        "--model2",
        type=Path,
        default=PROJECT_ROOT / "model" / "model2" / "inference_config.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "results" / "secondary_b" / f"feasibility_{_stamp()}",
    )
    parser.add_argument("--mode", choices=("input_rate", "capacity", "both"), default="both")
    parser.add_argument("--duration", type=float, default=35.0)
    parser.add_argument("--warmup", type=float, default=8.0)
    args = parser.parse_args(argv)

    pack = load_replay_pack(args.replay_pack)
    frames = pack["paths"]
    config = AppConfig(
        locator_model=Path(args.locator).resolve(),
        model2_config=Path(args.model2).resolve(),
        serial_enabled=False,
        inference_profile="FULL",
    )
    inspector = TwoStageInspector(config)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = {
        "probe": "secondary_b_feasibility_v1",
        "claim": "DEVELOPMENT / PILOT ONLY",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "arms": [],
        "verdicts": {},
    }

    # Warmup
    store = LatestFrame()
    img = cv2.imread(str(frames[0]))
    store.publish(img)
    run_worker_loop(store, inspector, 0.10, args.warmup, threading.Event())

    if args.mode in ("input_rate", "both"):
        # Same demand/arrival elevated; compare FULL vs SPARSE
        for arrival in (5.0, 15.0, 30.0):
            for profile, interval in (("FULL", 0.10), ("SPARSE", 0.20)):
                arm = run_arm(
                    inspector,
                    frames,
                    profile,
                    interval,
                    arrival_hz=arrival,
                    demand_hz=arrival,
                    duration_s=args.duration,
                    pressure=None,
                )
                arm["fault_model"] = "input_arrival_pressure"
                arm["pressure_tag"] = f"arrival_{arrival}hz"
                results["arms"].append(arm)

        # Heuristic: if served rate ~ unchanged across arrival rates for same profile → invalid
        full_rates = [
            a["lambda_served"]
            for a in results["arms"]
            if a.get("fault_model") == "input_arrival_pressure" and a["profile"] == "FULL"
        ]
        if full_rates and (max(full_rates) - min(full_rates)) < 0.5:
            results["verdicts"]["input_arrival_pressure"] = {
                "status": "INVALID",
                "reason": "lambda_served nearly invariant to arrival_hz under LatestFrame+interval",
            }
        else:
            results["verdicts"]["input_arrival_pressure"] = {
                "status": "VALID_CANDIDATE",
                "reason": "served rate or freshness moved with arrival_hz",
            }

    if args.mode in ("capacity", "both") and MultiGpuContention is not None:
        duties = (
            {"tag": "cap_20_80", "load_ms": 20, "idle_ms": 80},
            {"tag": "cap_40_60", "load_ms": 40, "idle_ms": 60},
            {"tag": "cap_60_40", "load_ms": 60, "idle_ms": 40},
            {"tag": "cap_75_25", "load_ms": 75, "idle_ms": 25},
            {"tag": "cap_90_10", "load_ms": 90, "idle_ms": 10},
        )
        # Fixed moderate arrival; profile-independent capacity pressure
        arrival = 10.0
        for duty in duties:
            for profile, interval in (("FULL", 0.10), ("SPARSE", 0.20)):
                pressure = MultiGpuContention(
                    kind="bandwidth",
                    replicas=2,
                    bytes_mb=512,
                    buffers=3,
                    streams=4,
                    load_ms=duty["load_ms"],
                    idle_ms=duty["idle_ms"],
                )
                arm = run_arm(
                    inspector,
                    frames,
                    profile,
                    interval,
                    arrival_hz=arrival,
                    demand_hz=arrival,
                    duration_s=args.duration,
                    pressure=pressure,
                )
                arm["fault_model"] = "service_capacity_pressure"
                arm["pressure_tag"] = duty["tag"]
                arm["pressure"] = duty
                results["arms"].append(arm)
        results["verdicts"]["service_capacity_pressure"] = {
            "status": "PROBED",
            "reason": "see arms for InspectionAge / pressure_miss vs duty; P1 TBD from analysis",
        }
    elif args.mode in ("capacity", "both"):
        results["verdicts"]["service_capacity_pressure"] = {
            "status": "SKIPPED",
            "reason": "MultiGpuContention unavailable",
        }

    results["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    # Compact table
    lines = [
        "# Secondary B feasibility (PILOT)",
        "",
        "| fault | tag | profile | age_p95 | lag_p95 | miss_rate | served | busy | wall_p50 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for a in results["arms"]:
        acc = a.get("accounting") or {}
        lines.append(
            "| {fault} | {tag} | {prof} | {age} | {lag} | {miss} | {served} | {busy} | {wall} |".format(
                fault=a.get("fault_model"),
                tag=a.get("pressure_tag"),
                prof=a.get("profile"),
                age=a["InspectionAge"].get("p95"),
                lag=a["FrameLag"].get("p95"),
                miss=acc.get("pressure_miss_rate"),
                served=a.get("lambda_served"),
                busy=a.get("worker_busy_fraction"),
                wall=(a.get("inspect_wall_ms") or {}).get("p50"),
            )
        )
    lines.append("")
    lines.append("## Verdicts")
    for k, v in results["verdicts"].items():
        lines.append(f"- **{k}**: `{v.get('status')}` — {v.get('reason')}")
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "verdicts": results["verdicts"], "n_arms": len(results["arms"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
