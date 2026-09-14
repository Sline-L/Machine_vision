"""Restart-only vs SPARSE under persistent real GPU pressure.

Does not call L2. Does not use inject_v5_latency. Locator stays PT_SAFE.
MTTR is t_MISSION_VERIFIED - t_fault, not Control HTTP 200.
"""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import random
import threading
import time
import uuid

from edgemedic.client import ControlClient
from edgemedic.gpu_pressure import GpuContention, INJECTOR_TYPE, INJECTOR_VERSION
from edgemedic.policy import V5_SLOW_MS, classify_fault
from edgemedic.provenance import (
    FAULT_REAL_RESOURCE_PRESSURE,
    collect_provenance,
    live_action,
    snapshot_telem,
    summarize_samples,
)


RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
ARMS = ("restart_only", "sparse")
RECOVERY = {
    "restart_only": ("restart_worker", {}),
    "sparse": ("set_inference_profile", {"profile": "SPARSE"}),
}

# Same observation window for both arms. V5/utility bars follow existing
# profile mission_spec in gp/verify.py (FULL 200 ms / SPARSE 220 ms).
WINDOW_S = 10.0
MIN_CYCLES = 8
MIN_VALID = 0.95
LOCATOR_P95_MS = 120.0
ELAPSED_P95_MS = 320.0
V5_P95_MS = {"FULL": 200.0, "SPARSE": 220.0}
UTILITY_MIN = {"FULL": 0.70, "SPARSE": 0.85}


def _now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def interleave_schedule(runs_per_arm, order="alternate", seed=1):
    n = max(1, int(runs_per_arm))
    if order == "alternate":
        schedule = []
        for _ in range(n):
            schedule.extend(ARMS)
        return schedule
    items = (["restart_only"] * n) + (["sparse"] * n)
    random.Random(int(seed)).shuffle(items)
    return items


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
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def mission_loss(points, t_fault, t_end):
    """L_M = sum (1 - U_k) dt from t_fault to t_end. Smaller is better."""
    rows = [(float(t), item) for t, item in points if t_fault <= float(t) <= t_end]
    if not rows:
        return 0.0
    loss = 0.0
    for index, (stamp, telem) in enumerate(rows):
        nxt = rows[index + 1][0] if index + 1 < len(rows) else t_end
        dt = max(0.0, float(nxt) - float(stamp))
        utility = telem.get("utility")
        if utility is None:
            utility = 0.0
        loss += (1.0 - float(utility)) * dt
    return round(loss, 4)


def downtime_s(points, t_fault, t_end):
    rows = [(float(t), item) for t, item in points if t_fault <= float(t) <= t_end]
    if not rows:
        return 0.0
    down = 0.0
    for index, (stamp, telem) in enumerate(rows):
        nxt = rows[index + 1][0] if index + 1 < len(rows) else t_end
        dt = max(0.0, float(nxt) - float(stamp))
        valid = bool(telem.get("output_valid")) and bool(telem.get("inspection_active"))
        if not valid:
            down += dt
    return round(down, 4)


def window_stats(points, t_end, window_s=WINDOW_S):
    start = float(t_end) - float(window_s)
    rows = [item for stamp, item in points if start < float(stamp) <= float(t_end)]
    valid = [item for item in rows if item.get("output_valid")]
    loc = [item.get("locator_latency_ms") for item in valid]
    v5 = [item.get("v5_latency_ms") for item in valid]
    elapsed = []
    for item in valid:
        loc_ms = item.get("locator_latency_ms")
        v5_ms = item.get("v5_latency_ms")
        if loc_ms is None or v5_ms is None:
            continue
        elapsed.append(float(loc_ms) + float(v5_ms))
    last = rows[-1] if rows else {}
    return {
        "n": len(rows),
        "output_valid_ratio": None if not rows else len(valid) / len(rows),
        "locator_p95_ms": _percentile(loc, 95),
        "v5_p95_ms": _percentile(v5, 95),
        "elapsed_p95_ms": _percentile(elapsed, 95),
        "utility": last.get("utility"),
        "profile": last.get("profile"),
        "inspection_active": last.get("inspection_active"),
    }


def mission_ok(stats, profile):
    if int(stats.get("n") or 0) < MIN_CYCLES:
        return False, "cycles"
    ratio = stats.get("output_valid_ratio")
    if ratio is None or float(ratio) < MIN_VALID:
        return False, "valid_ratio"
    loc = stats.get("locator_p95_ms")
    if loc is not None and float(loc) > LOCATOR_P95_MS:
        return False, "locator_p95"
    v5 = stats.get("v5_p95_ms")
    limit = V5_P95_MS.get(profile, V5_P95_MS["FULL"])
    if v5 is not None and float(v5) > limit:
        return False, "v5_p95"
    elapsed = stats.get("elapsed_p95_ms")
    if elapsed is not None and float(elapsed) > ELAPSED_P95_MS:
        return False, "elapsed_p95"
    utility = stats.get("utility")
    umin = UTILITY_MIN.get(profile, UTILITY_MIN["FULL"])
    if utility is not None and float(utility) < umin:
        return False, "utility"
    if not stats.get("inspection_active"):
        return False, "inactive"
    return True, None


def first_mission_time(points, t_fault, profile):
    stamps = [float(stamp) for stamp, _item in points]
    for stamp in stamps:
        if stamp < t_fault + WINDOW_S:
            continue
        ok, _reason = mission_ok(window_stats(points, stamp), profile)
        if ok:
            return stamp
    return None


class _Sampler:
    def __init__(self, client, interval=0.25):
        self.client = client
        self.interval = float(interval)
        self.points = []
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="a3-sampler", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                snapshot = self.client.get_state()
                self.points.append((time.monotonic(), snapshot_telem(snapshot), snapshot))
            except Exception:
                pass
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        return list(self.points)


def _profile(snapshot):
    return (snapshot.get("mission") or {}).get("current_profile") or "FULL"


def _backend(snapshot):
    return (snapshot.get("locator") or {}).get("backend")


def _reset_healthy(client, url, warmup_s):
    live_action(url, "set_locator_profile", {"profile": "pt_safe"}, source="reflex")
    live_action(url, "set_inference_profile", {"profile": "FULL"}, source="reflex")
    time.sleep(max(0.0, float(warmup_s)))
    snapshot = client.get_state()
    return snapshot


def _healthy_ok(summary, snapshot, args, ref_temp):
    profile = _profile(snapshot)
    backend = _backend(snapshot)
    v5_p95 = ((summary.get("scratch_v5") or {}).get("p95"))
    temp = (snapshot.get("system") or {}).get("temperature_c")
    errors = int((snapshot.get("scratch_v5") or {}).get("error_count") or 0)
    if profile != "FULL" or (backend or "pt") != "pt":
        return False, f"not FULL/pt ({profile}/{backend})"
    if errors:
        return False, "worker errors"
    if v5_p95 is None or float(v5_p95) > float(args.baseline_v5_p95_max):
        return False, f"v5 p95 {v5_p95} above {args.baseline_v5_p95_max}"
    if temp is not None and float(temp) > float(args.temp_max_c):
        return False, f"temp {temp}"
    if ref_temp is not None and temp is not None and abs(float(temp) - float(ref_temp)) > float(args.temp_delta_c):
        return False, f"temp drift {temp} vs {ref_temp}"
    return True, None


def _wait_overload(client, timeout_s):
    deadline = time.monotonic() + float(timeout_s)
    while time.monotonic() < deadline:
        snapshot = client.get_state()
        if classify_fault(snapshot) == "V5_OVERLOAD":
            return time.monotonic(), snapshot
        time.sleep(0.2)
    return None, client.get_state()


def _summarize_arm(rows):
    n = len(rows)
    mission = sum(1 for row in rows if row.get("recovery_success"))
    mttrs = [row["mttr_s"] for row in rows if row.get("mttr_s") is not None]
    losses = [row["mission_loss"] for row in rows]
    return {
        "n": n,
        "asr_mission": None if not n else round(mission / n, 4),
        "mttr_s_mean": None if not mttrs else round(sum(mttrs) / len(mttrs), 4),
        "mttr_censored_n": sum(1 for row in rows if row.get("mttr_censored")),
        "mission_loss_mean": None if not losses else round(sum(losses) / len(losses), 4),
    }


def run_trial(arm, args, pressure, client, ref_temp):
    url = args.control_url
    trial_id = uuid.uuid4().hex[:8]
    pressure.stop()
    baseline_snap = _reset_healthy(client, url, args.warmup_s)
    healthy = []
    deadline = time.monotonic() + float(args.healthy_sample_s)
    while time.monotonic() <= deadline:
        snapshot = client.get_state()
        healthy.append(snapshot_telem(snapshot))
        time.sleep(0.25)
    healthy_summary = summarize_samples(healthy)
    ok, reason = _healthy_ok(healthy_summary, baseline_snap, args, ref_temp)
    if not ok:
        return {
            "trial_id": trial_id,
            "arm": arm,
            "aborted": True,
            "abort_reason": f"reset failed: {reason}",
            "healthy": healthy_summary,
        }
    started = pressure.start()
    if not pressure.alive():
        return {"trial_id": trial_id, "arm": arm, "aborted": True, "abort_reason": "injector died"}
    t_fault, detect_snap = _wait_overload(client, args.detect_timeout_s)
    if t_fault is None:
        pressure.stop()
        return {
            "trial_id": trial_id,
            "arm": arm,
            "aborted": True,
            "abort_reason": "V5_OVERLOAD not reached",
            "detect": snapshot_telem(detect_snap),
            "injector": started,
        }
    sampler = _Sampler(client, interval=args.sample_interval_s)
    sampler.start()
    name, params = RECOVERY[arm]
    recover_deadline = t_fault + float(args.recover_timeout_s)
    action_result = client.post_action(
        name,
        params=params,
        source="reflex",
        request_id=f"a3-{arm}-{trial_id}",
        timeout=max(35.0, float(args.recover_timeout_s) + 5.0),
    )
    t_action = time.monotonic()
    expect_profile = "SPARSE" if arm == "sparse" else "FULL"
    while time.monotonic() < recover_deadline:
        pts = [(stamp, telem) for stamp, telem, _snap in list(sampler.points)]
        if first_mission_time(pts, t_fault, expect_profile) is not None:
            break
        time.sleep(0.25)
    points = [(stamp, telem) for stamp, telem, _snap in sampler.stop()]
    t_end = time.monotonic()
    injector_alive = pressure.alive()
    pressure.stop()
    t_mission = first_mission_time(points, t_fault, expect_profile)
    success = t_mission is not None and t_mission <= recover_deadline
    mttr = None if not success else round(t_mission - t_fault, 4)
    close = t_mission if success else min(t_end, recover_deadline)
    after = [telem for stamp, telem in points if stamp >= t_fault]
    return {
        "trial_id": trial_id,
        "arm": arm,
        "aborted": False,
        "t_fault_monotonic": t_fault,
        "t_action_monotonic": t_action,
        "t_mission_monotonic": t_mission,
        "recovery_success": success,
        "mttr_s": mttr,
        "mttr_censored": not success,
        "mission_loss": mission_loss(points, t_fault, close),
        "downtime_s": downtime_s(points, t_fault, close),
        "detect": snapshot_telem(detect_snap),
        "healthy": healthy_summary,
        "after": summarize_samples(after),
        "action": {
            "name": name,
            "params": params,
            "accepted": action_result.get("accepted"),
            "executed": action_result.get("executed"),
            "verify_level": action_result.get("verify_level"),
            "error": action_result.get("error"),
            "control_recovery_success": action_result.get("recovery_success"),
        },
        "injector_alive_through_recovery": injector_alive,
        "injector": started,
        "experimentally_validated": False,
        "a3_claim": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="A3 Restart-only vs SPARSE under real GPU pressure")
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--replay-pack", type=Path, default=Path("tests/replay"))
    parser.add_argument("--phase", choices=("pilot", "formal"), default="pilot")
    parser.add_argument("--runs-per-arm", type=int, default=3)
    parser.add_argument("--order", choices=("alternate", "shuffle"), default="alternate")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--warmup-s", type=float, default=15.0)
    parser.add_argument("--healthy-sample-s", type=float, default=15.0)
    parser.add_argument("--detect-timeout-s", type=float, default=45.0)
    parser.add_argument("--recover-timeout-s", type=float, default=90.0)
    parser.add_argument("--sample-interval-s", type=float, default=0.25)
    parser.add_argument("--baseline-v5-p95-max", type=float, default=190.0)
    parser.add_argument("--temp-max-c", type=float, default=72.0)
    parser.add_argument("--temp-delta-c", type=float, default=6.0)
    parser.add_argument("--matrix", type=int, default=1024)
    parser.add_argument("--sleep-ms", type=float, default=0.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    client = ControlClient(args.control_url, timeout=5.0)
    client.get_state()
    pressure = GpuContention(matrix=args.matrix, sleep_ms=args.sleep_ms)
    schedule = interleave_schedule(args.runs_per_arm, order=args.order, seed=args.seed)
    injector_cfg = pressure.config()
    exp_config = {
        "kind": "a3_restart_vs_sparse",
        "phase": args.phase,
        "question": "persistent real V5 pressure: restart_only vs SPARSE mission recovery",
        "l2": False,
        "locator_backend": "pt_safe",
        "initial_profile": "FULL",
        "fault_mode": FAULT_REAL_RESOURCE_PRESSURE,
        "fault_injector_type": INJECTOR_TYPE,
        "fault_injector_version": INJECTOR_VERSION,
        "fault_injector_config": injector_cfg,
        "fault_injector_hash": pressure.hash(),
        "warmup_s": args.warmup_s,
        "healthy_sample_s": args.healthy_sample_s,
        "detect_timeout_s": args.detect_timeout_s,
        "recover_timeout_s": args.recover_timeout_s,
        "window_s": WINDOW_S,
        "runs_per_arm": args.runs_per_arm,
        "order": args.order,
        "seed": args.seed,
        "schedule": schedule,
        "replay_pack_dir": str(args.replay_pack),
        "matrix": args.matrix,
        "sleep_ms": args.sleep_ms,
    }
    rows = []
    ref_temp = None
    try:
        for arm in schedule:
            row = run_trial(arm, args, pressure, client, ref_temp)
            if not row.get("aborted") and ref_temp is None:
                ref_temp = ((row.get("healthy") or {}).get("temperature_c"))
            rows.append(row)
            time.sleep(2.0)
    finally:
        pressure.stop()
        try:
            _reset_healthy(client, args.control_url, 2.0)
        except Exception:
            pass
    by_arm = {arm: [row for row in rows if row.get("arm") == arm and not row.get("aborted")] for arm in ARMS}
    payload = {
        "stage": "a3-restart-vs-sparse",
        "phase": args.phase,
        "question": exp_config["question"],
        "l2": False,
        "experimentally_validated": False,
        "a3_claim": False,
        "schedule": schedule,
        "arms": {arm: _summarize_arm(by_arm[arm]) for arm in ARMS},
        "aborted": [row for row in rows if row.get("aborted")],
        "runs": rows,
        "provenance": collect_provenance(
            reasoner="none",
            runtime_mode="dataset_replay",
            snapshot=client.get_state(),
            fault_mode=FAULT_REAL_RESOURCE_PRESSURE,
            experiment_config=exp_config,
            replay_pack_dir=args.replay_pack,
        ),
        "note": "Pressure stays on through recovery/timeout. MTTR uses independent mission window, not action HTTP return. Do not retune SPARSE or mission bars from this run.",
    }
    out = args.out or (RESULTS_ROOT / f"a3_{args.phase}_{_now_stamp()}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = {key: value for key, value in payload.items() if key != "runs"}
    brief["out"] = str(out)
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    if payload["aborted"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
