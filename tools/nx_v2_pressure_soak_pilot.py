#!/usr/bin/env python3
"""ENGINEERING ONLY — LATENCY_DEGRADED_V2 lean pressure pilot on NX.

NOT MISSION APPROVED.
NOT A3 EFFECTIVENESS.

Lean stages (A–F) run first with hard timeouts. Soak is optional and
only starts after A–F PASS. Transition loop is skipped by default.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import os
import resource
import statistics
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

BANNER = "ENGINEERING ONLY — NOT MISSION APPROVED — NOT A3 EFFECTIVENESS"
ADMISSION_P95_MS = 190.0
V5_SLOW_MS = 200.0
HOLD_S = 2.0

# Engineering hard timeouts (seconds). Not production MTTR.
TIMEOUT_MODEL_LOAD_S = 120.0
TIMEOUT_WARMUP_S = 120.0
TIMEOUT_FIRST_INFER_S = 60.0
TIMEOUT_TRANSITION_S = 180.0
TIMEOUT_WINDOW_MARGIN_S = 30.0

QUALIFIED = {
    "kind": "bandwidth",
    "bytes_mb": 512,
    "buffers": 3,
    "streams": 4,
    "load_ms": 100,
    "idle_ms": 0,
    "replicas": 3,
}

PREVIOUS_RUN_EVENT = {
    "id": "prev_run_20260915_153233",
    "classification": "SUSPICIOUS_ENGINEERING_EVENT",
    "conclusion": "NO RESEARCH CONCLUSION DRAWN",
    "buffering_vs_hang": "UNDETERMINED — cannot assert stdout buffering vs actual runtime hang",
    "observations": {
        "started_at_local": "2026-09-15T15:32:33+08:00",
        "aborted_at_local": "2026-09-15T16:09:02+08:00",
        "elapsed_before_abort_s": 2184,
        "flushed_log_bytes": 57,
        "flushed_output": ["HEAD=9e08d33", "===START PILOT ...==="],
        "rss_kib_observed": 1978992,
        "rss_unchanged": True,
        "cpu_pct_observed": 69.2,
        "suspected_stage": "load/warmup (exact stage unknown due buffered logging)",
        "run_aborted_manually": True,
    },
}


def log(msg: str = "") -> None:
    print(msg, flush=True)


def _pct(values, p):
    ordered = sorted(float(v) for v in values if v is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def _mean(values):
    nums = [float(v) for v in values if v is not None]
    return None if not nums else statistics.fmean(nums)


def process_snapshot():
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        with proc.oneshot():
            return {
                "rss_mib": proc.memory_info().rss / (1024 * 1024),
                "threads": proc.num_threads(),
                "cpu_pct": proc.cpu_percent(interval=0.0),
            }
    except Exception:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "rss_mib": float(usage.ru_maxrss) / 1024.0,
            "threads": None,
            "cpu_pct": None,
        }


def gpu_snapshot():
    out = {"tegrastats": {}}
    try:
        from edgemedic.gpu_pressure import read_gpu_clock_mhz, read_emc_mhz, read_tegrastats, read_power_mode

        out["gpu_clock_mhz"] = read_gpu_clock_mhz()
        out["emc_mhz"] = read_emc_mhz()
        out["power_mode"] = read_power_mode()
        out["tegrastats"] = read_tegrastats() or {}
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    try:
        raw = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
        ).strip()
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) >= 4 and all(p not in {"[N/A]", "N/A", ""} for p in parts[:4]):
            out["temp_c"] = float(parts[0])
            out["gpu_util_pct"] = float(parts[1])
            out["mem_used_mib"] = float(parts[2])
            out["mem_total_mib"] = float(parts[3])
    except Exception as exc:  # noqa: BLE001
        out["nvidia_smi_error"] = str(exc)
    # Jetson fallback: parse tegrastats line for temp if present
    try:
        completed = subprocess.run(
            ["tegrastats", "--interval", "200"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
    except Exception:
        completed = None
    if completed is not None:
        text = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if text:
            line = text.splitlines()[-1]
            out["tegrastats_line"] = line[:500]
            import re

            gpu_t = re.search(r"gpu@([0-9.]+)C", line)
            if gpu_t:
                out["temp_c"] = float(gpu_t.group(1))
            gr3d = re.search(r"GR3D_FREQ\s+(\d+)%", line)
            if gr3d:
                out["gpu_util_pct"] = float(gr3d.group(1))
    return out


def dump_thread_stacks() -> str:
    import io

    buf = io.StringIO()
    faulthandler.dump_traceback(file=buf, all_threads=True)
    # Also capture current-thread traceback frames via sys._current_frames
    buf.write("\n--- sys._current_frames ---\n")
    for tid, frame in sys._current_frames().items():
        buf.write(f"Thread {tid}:\n")
        buf.write("".join(traceback.format_stack(frame)))
    return buf.getvalue()


class StageRunner:
    """Run stages on the main thread (CUDA-safe) with a hard watchdog timeout.

    On timeout the watchdog dumps stacks/diagnostics to a sidecar JSON and
    calls os._exit(3). Soft FuturesTimeout is intentionally avoided so model
    objects are never created on a worker thread and used on another.
    """

    def __init__(self, timeout_dump_path: Path | None = None):
        self.stages = []
        self.last_successful = None
        self.current = None
        self.t0 = time.monotonic()
        self.timeout_dump_path = timeout_dump_path
        self._lock = threading.Lock()
        self._watchdog = None

    def _cancel_watchdog(self):
        # Caller must hold self._lock (non-reentrant Lock).
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None

    def _arm_watchdog(self, name: str, timeout_s: float, profile):
        def _fire():
            elapsed = time.monotonic() - self.t0
            diagnostics = {
                "current_stage": name,
                "last_successful_stage": self.last_successful,
                "wall_elapsed_s_since_pilot_start": round(elapsed, 3),
                "stage_timeout_s": timeout_s,
                "process": process_snapshot(),
                "gpu": gpu_snapshot(),
                "active_or_requested_profile": profile,
                "thread_stacks": dump_thread_stacks(),
                "note": "hard watchdog fired; process exiting to avoid infinite wait",
            }
            log(f"[FAIL] {name} TIMEOUT after {timeout_s:.0f}s (watchdog)")
            try:
                log(json.dumps({k: v for k, v in diagnostics.items() if k != "thread_stacks"}, indent=2, default=str))
            except Exception:
                pass
            if self.timeout_dump_path is not None:
                try:
                    self.timeout_dump_path.write_text(
                        json.dumps(diagnostics, indent=2, default=str),
                        encoding="utf-8",
                    )
                    log(f"wrote timeout dump {self.timeout_dump_path}")
                except Exception as exc:  # noqa: BLE001
                    log(f"timeout dump write failed: {exc}")
            # Hard stop — CUDA hang cannot be interrupted cooperatively.
            os._exit(3)

        with self._lock:
            self._cancel_watchdog()
            self._watchdog = threading.Timer(float(timeout_s), _fire)
            self._watchdog.daemon = True
            self._watchdog.start()

    def run(self, name: str, timeout_s: float, fn, *, profile=None):
        self.current = name
        started = time.monotonic()
        log(f"[START] {name} t={started - self.t0:.3f}s timeout={timeout_s:.0f}s")
        entry = {
            "stage": name,
            "profile": profile,
            "timeout_s": timeout_s,
            "started_monotonic": started,
            "started_wall": datetime.now(timezone.utc).isoformat(),
        }
        self._arm_watchdog(name, timeout_s, profile)
        try:
            result = fn()  # main thread — required for CUDA affinity
            elapsed = time.monotonic() - started
            entry.update({"status": "PASS", "elapsed_s": round(elapsed, 3)})
            self.stages.append(entry)
            self.last_successful = name
            log(f"[PASS] {name} elapsed={elapsed:.3f}s")
            return result
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - started
            entry.update(
                {
                    "status": "FAIL",
                    "elapsed_s": round(elapsed, 3),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc()[-3000:],
                }
            )
            self.stages.append(entry)
            log(f"[FAIL] {name} {entry['error']}")
            raise
        finally:
            with self._lock:
                self._cancel_watchdog()


def load_crops(replay_root: Path, limit: int = 40):
    frames = sorted((replay_root / "frames").glob("*.jpg"))
    crops = []
    for path in frames[:limit]:
        image = cv2.imread(str(path))
        if image is None:
            continue
        h, w = image.shape[:2]
        side = min(h, w)
        y0 = (h - side) // 2
        x0 = (w - side) // 2
        crops.append(image[y0 : y0 + side, x0 : x0 + side])
    if len(crops) < 5:
        raise SystemExit(f"too few crops under {replay_root}")
    return crops


def identity_of(runtime):
    cfg = runtime.config
    classifiers = cfg.get("classifiers") or []
    return {
        "scratch_version": cfg.get("version"),
        "classifier_count": len(classifiers),
        "classifier_shas": [str(c.get("sha256") or "").lower() for c in classifiers],
        "detector_sha": str((cfg.get("detector") or {}).get("sha256") or "").lower(),
        "threshold": float(cfg.get("default_threshold")),
        "fusion_alpha": float((cfg.get("fusion") or {}).get("alpha")),
        "cls2_expected_zero": len(classifiers) == 1,
    }


def load_runtime_no_warmup(profile: str):
    from gp.scratch_v5 import ScratchV5Runtime
    from gp.capability_v2 import FULL_INFERENCE_CONFIG, V2_INFERENCE_CONFIG, validate_frozen_artifacts

    if profile == "FULL":
        path = FULL_INFERENCE_CONFIG
    elif profile == "LATENCY_DEGRADED_V2":
        validate_frozen_artifacts()
        path = V2_INFERENCE_CONFIG
    else:
        raise ValueError(profile)
    return ScratchV5Runtime(path, warmup=False), path


def warmup_runtime(runtime):
    runtime._warmup()


def first_inference(runtime, crop):
    pred = runtime.predict(crop)
    if not np.isfinite(pred.defect_score):
        raise RuntimeError("non-finite defect_score on first inference")
    return pred


def run_window(runtime, crops, duration_s: float, label: str, injector=None):
    samples = []
    t0 = time.monotonic()
    deadline = t0 + float(duration_s)
    idx = 0
    exceptions = 0
    overload_events = []
    while time.monotonic() < deadline:
        crop = crops[idx % len(crops)]
        idx += 1
        started = time.perf_counter()
        try:
            pred = runtime.predict(crop)
            wall = (time.perf_counter() - started) * 1000.0
            stage = (
                pred.classifier1_latency_ms
                + pred.classifier2_latency_ms
                + pred.detector_latency_ms
                + pred.fusion_latency_ms
            )
            ok = all(
                np.isfinite(v)
                for v in (pred.defect_score, pred.classifier_probability, pred.detector_probability)
            )
            samples.append(
                {
                    "t": time.monotonic(),
                    "wall_ms": wall,
                    "stage_ms": stage,
                    "cls1_ms": pred.classifier1_latency_ms,
                    "cls2_ms": pred.classifier2_latency_ms,
                    "det_ms": pred.detector_latency_ms,
                    "valid": bool(ok),
                    "score": float(pred.defect_score),
                }
            )
            overload_events.append((time.monotonic(), wall >= V5_SLOW_MS))
        except Exception:  # noqa: BLE001
            exceptions += 1
            overload_events.append((time.monotonic(), False))
        if injector is not None and not injector.alive():
            break
    t1 = time.monotonic()
    walls = [s["wall_ms"] for s in samples]
    stages = [s["stage_ms"] for s in samples]
    valid = [s for s in samples if s["valid"]]
    onset = None
    hold_start = None
    for stamp, overloaded in overload_events:
        if overloaded:
            if hold_start is None:
                hold_start = stamp
            if stamp - hold_start >= HOLD_S and onset is None:
                onset = hold_start
        else:
            hold_start = None
    return {
        "label": label,
        "duration_s": round(t1 - t0, 3),
        "n": len(samples),
        "exceptions": exceptions,
        "valid_ratio": None if not samples else len(valid) / len(samples),
        "inspect_rate_hz": None if t1 <= t0 else len(samples) / (t1 - t0),
        "wall_ms": {
            "p50": _pct(walls, 50),
            "p95": _pct(walls, 95),
            "max": None if not walls else max(walls),
            "mean": _mean(walls),
        },
        "stage_ms": {
            "p50": _pct(stages, 50),
            "p95": _pct(stages, 95),
            "max": None if not stages else max(stages),
            "mean": _mean(stages),
        },
        "cls1_p95": _pct([s["cls1_ms"] for s in samples], 95),
        "cls2_p95": _pct([s["cls2_ms"] for s in samples], 95),
        "det_p95": _pct([s["det_ms"] for s in samples], 95),
        "mission_latency_gate_190": None
        if not walls
        else bool(_pct(walls, 95) is not None and _pct(walls, 95) < ADMISSION_P95_MS),
        "sustained_overload_onset": onset,
        "sustained_overload": onset is not None,
        "identity": identity_of(runtime),
        "gpu": gpu_snapshot(),
        "process": process_snapshot(),
        "injector_alive": None if injector is None else bool(injector.alive()),
    }, samples


def make_pressure():
    from edgemedic.multi_pressure import MultiGpuContention

    return MultiGpuContention(
        replicas=QUALIFIED["replicas"],
        kind=QUALIFIED["kind"],
        bytes_mb=QUALIFIED["bytes_mb"],
        buffers=QUALIFIED["buffers"],
        streams=QUALIFIED["streams"],
        load_ms=QUALIFIED["load_ms"],
        idle_ms=QUALIFIED["idle_ms"],
    )


def bringup_profile(stages: StageRunner, profile: str, crop):
    """Load → warmup → first inference with hard timeouts. Returns runtime."""
    runtime, path = stages.run(
        f"load {profile} artifacts",
        TIMEOUT_MODEL_LOAD_S,
        lambda: load_runtime_no_warmup(profile),
        profile=profile,
    )
    stages.run(
        f"{profile} warmup",
        TIMEOUT_WARMUP_S,
        lambda: warmup_runtime(runtime),
        profile=profile,
    )
    stages.run(
        f"{profile} first inference",
        TIMEOUT_FIRST_INFER_S,
        lambda: first_inference(runtime, crop),
        profile=profile,
    )
    return runtime, path


def cool(seconds: float):
    time.sleep(max(0.0, float(seconds)))


def main():
    faulthandler.enable(all_threads=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, default=Path("/home/jetson/Projects/Machine_vision/tests/replay"))
    parser.add_argument("--healthy-s", type=float, default=40.0)
    parser.add_argument("--pressure-s", type=float, default=45.0)
    parser.add_argument("--cool-s", type=float, default=45.0)
    parser.add_argument("--soak-s", type=float, default=1800.0)
    parser.add_argument("--run-soak", action="store_true", help="Run soak only after A-F PASS")
    parser.add_argument("--skip-pressure", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    log(BANNER)
    log(f"pid={os.getpid()} python={sys.executable}")
    log(f"PREVIOUS_RUN_EVENT={json.dumps(PREVIOUS_RUN_EVENT, default=str)}")

    root = Path(__file__).resolve().parents[1]
    out_dir = args.out_dir or (root / "docs" / "capability-extraction" / "v3")
    out_dir.mkdir(parents=True, exist_ok=True)
    stages = StageRunner(timeout_dump_path=out_dir / "v2-pressure-pilot-timeout-dump.json")

    crops = stages.run("runtime init / load crops", 60.0, lambda: load_crops(args.replay))

    from gp.profiles import apply_to_config, ProfileError
    from gp.config import AppConfig
    from gp.capability_v2 import load_frozen

    def _prod_check():
        try:
            apply_to_config(AppConfig(), "LATENCY_DEGRADED_V2", engineering_mode=False)
            return False
        except ProfileError:
            return True

    production_rejected = stages.run("production reject check", 30.0, _prod_check)
    if not production_rejected:
        raise SystemExit("production path unexpectedly allowed V2")

    report = {
        "mode": "ENGINEERING ONLY",
        "mission_approved": False,
        "a3_effectiveness": "NOT ESTABLISHED",
        "banner": BANNER,
        "branch_intent": "srtp-agent/v2-pressure-pilot",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "previous_run_event": PREVIOUS_RUN_EVENT,
        "qualified_injector": QUALIFIED,
        "admission_p95_ms": ADMISSION_P95_MS,
        "timeouts_s": {
            "model_load": TIMEOUT_MODEL_LOAD_S,
            "warmup": TIMEOUT_WARMUP_S,
            "first_inference": TIMEOUT_FIRST_INFER_S,
            "transition": TIMEOUT_TRANSITION_S,
        },
        "production_rejected": production_rejected,
        "frozen_config_hash": load_frozen()["config_hash"],
        "n_crops": len(crops),
        "lean": {},
        "soak": None,
        "stages": [],
        "verdict": {},
        "engineering_blocker": None,
    }

    lean_pass = False
    try:
        # A. FULL healthy
        log("=== A FULL healthy sanity ===")
        full_rt, _ = bringup_profile(stages, "FULL", crops[0])
        healthy_full = stages.run(
            "FULL healthy window",
            args.healthy_s + TIMEOUT_WINDOW_MARGIN_S,
            lambda: run_window(full_rt, crops, args.healthy_s, "healthy_FULL")[0],
            profile="FULL",
        )
        log(json.dumps({"wall_p95": healthy_full["wall_ms"]["p95"], "gate": healthy_full["mission_latency_gate_190"]}))
        del full_rt
        cool(10)

        # B. V2 healthy
        log("=== B V2 healthy sanity ===")
        v2_loaded = stages.run(
            "switch V2 (load artifacts)",
            TIMEOUT_TRANSITION_S,
            lambda: load_runtime_no_warmup("LATENCY_DEGRADED_V2"),
            profile="LATENCY_DEGRADED_V2",
        )
        v2_rt, _ = v2_loaded
        stages.run(
            "V2 warmup",
            TIMEOUT_WARMUP_S,
            lambda: warmup_runtime(v2_rt),
            profile="LATENCY_DEGRADED_V2",
        )
        stages.run(
            "V2 first inference",
            TIMEOUT_FIRST_INFER_S,
            lambda: first_inference(v2_rt, crops[0]),
            profile="LATENCY_DEGRADED_V2",
        )
        healthy_v2 = stages.run(
            "V2 healthy window",
            args.healthy_s + TIMEOUT_WINDOW_MARGIN_S,
            lambda: run_window(v2_rt, crops, args.healthy_s, "healthy_V2")[0],
            profile="LATENCY_DEGRADED_V2",
        )
        log(
            json.dumps(
                {
                    "wall_p95": healthy_v2["wall_ms"]["p95"],
                    "cls2_p95": healthy_v2["cls2_p95"],
                    "gate": healthy_v2["mission_latency_gate_190"],
                }
            )
        )
        if float(healthy_v2["cls2_p95"] or 0) > 0.01:
            raise SystemExit("V2 topology failed: cls2 latency not zero")
        del v2_rt
        cool(10)

        report["lean"]["healthy"] = {"FULL": healthy_full, "LATENCY_DEGRADED_V2": healthy_v2}

        pressure_arm = {}
        switch = None
        if not args.skip_pressure:
            # C+D same injector
            log("=== C/D FULL then V2 under identical pressure ===")
            def _start_injector():
                inj = make_pressure()
                started_meta = inj.start()
                if not inj.alive():
                    raise RuntimeError("injector died at start")
                return inj, started_meta

            pressure, started = stages.run("injector start", 60.0, _start_injector)
            inj_meta = {
                "start": started,
                "config": pressure.config(),
                "hash": pressure.hash(),
                "alive_at_start": pressure.alive(),
            }
            log(f"[INFO] injector alive={pressure.alive()} hash={inj_meta['hash']}")
            cool(5)

            full_rt, _ = bringup_profile(stages, "FULL", crops[0])
            full_p = stages.run(
                "FULL pressure window",
                args.pressure_s + TIMEOUT_WINDOW_MARGIN_S,
                lambda: run_window(full_rt, crops, args.pressure_s, "pressure_FULL", injector=pressure)[0],
                profile="FULL",
            )
            full_p["injector_alive_end"] = pressure.alive()
            pressure_arm["FULL"] = full_p
            log(
                json.dumps(
                    {
                        "profile": "FULL",
                        "wall_p95": full_p["wall_ms"]["p95"],
                        "gate190": full_p["mission_latency_gate_190"],
                        "injector_alive": full_p["injector_alive_end"],
                        "sustained_overload": full_p["sustained_overload"],
                    }
                )
            )
            del full_rt
            cool(5)

            # E. engineering switch under same pressure (keep injector ON)
            log("=== E engineering FULL→V2 switch under pressure ===")
            switch = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "injector_alive_before_switch": pressure.alive(),
            }
            t_switch0 = time.monotonic()

            def _switch_load():
                return load_runtime_no_warmup("LATENCY_DEGRADED_V2")

            v2_loaded = stages.run(
                "switch V2 under pressure (load)",
                TIMEOUT_TRANSITION_S,
                _switch_load,
                profile="LATENCY_DEGRADED_V2",
            )
            v2_rt, _ = v2_loaded
            stages.run(
                "V2 warmup under pressure",
                TIMEOUT_WARMUP_S,
                lambda: warmup_runtime(v2_rt),
                profile="LATENCY_DEGRADED_V2",
            )
            stages.run(
                "V2 first inference under pressure",
                TIMEOUT_FIRST_INFER_S,
                lambda: first_inference(v2_rt, crops[0]),
                profile="LATENCY_DEGRADED_V2",
            )
            switch["profile_activation_s"] = round(time.monotonic() - t_switch0, 3)
            switch["injector_alive_after_activation"] = pressure.alive()

            v2_p = stages.run(
                "V2 pressure window",
                args.pressure_s + TIMEOUT_WINDOW_MARGIN_S,
                lambda: run_window(v2_rt, crops, args.pressure_s, "pressure_V2", injector=pressure)[0],
                profile="LATENCY_DEGRADED_V2",
            )
            v2_p["injector_alive_end"] = pressure.alive()
            pressure_arm["LATENCY_DEGRADED_V2"] = v2_p
            switch["v2_under_pressure"] = v2_p
            log(
                json.dumps(
                    {
                        "profile": "LATENCY_DEGRADED_V2",
                        "wall_p95": v2_p["wall_ms"]["p95"],
                        "gate190": v2_p["mission_latency_gate_190"],
                        "cls2_p95": v2_p["cls2_p95"],
                        "injector_alive": v2_p["injector_alive_end"],
                    }
                )
            )

            # F. rollback FULL while pressure remains
            log("=== F rollback FULL under pressure ===")
            t_rb0 = time.monotonic()
            del v2_rt
            full_loaded = stages.run(
                "rollback FULL load under pressure",
                TIMEOUT_TRANSITION_S,
                lambda: load_runtime_no_warmup("FULL"),
                profile="FULL",
            )
            full_rt, _ = full_loaded
            stages.run(
                "rollback FULL warmup",
                TIMEOUT_WARMUP_S,
                lambda: warmup_runtime(full_rt),
                profile="FULL",
            )
            stages.run(
                "rollback FULL first inference",
                TIMEOUT_FIRST_INFER_S,
                lambda: first_inference(full_rt, crops[0]),
                profile="FULL",
            )
            switch["rollback_load_s"] = round(time.monotonic() - t_rb0, 3)
            rolled = stages.run(
                "rollback FULL window under pressure",
                30.0 + TIMEOUT_WINDOW_MARGIN_S,
                lambda: run_window(full_rt, crops, 30.0, "rollback_FULL", injector=pressure)[0],
                profile="FULL",
            )
            switch["full_after_rollback"] = rolled
            switch["injector_alive_after_rollback"] = pressure.alive()
            switch["injector"] = inj_meta
            pressure.stop()
            switch["injector_alive_after_stop"] = pressure.alive()
            del full_rt

            report["lean"]["pressure"] = {
                "order": ["FULL", "LATENCY_DEGRADED_V2"],
                "arms": pressure_arm,
                "injector": inj_meta,
                "delta_p95": None
                if pressure_arm["FULL"]["wall_ms"]["p95"] is None
                or pressure_arm["LATENCY_DEGRADED_V2"]["wall_ms"]["p95"] is None
                else pressure_arm["LATENCY_DEGRADED_V2"]["wall_ms"]["p95"]
                - pressure_arm["FULL"]["wall_ms"]["p95"],
                "ratio_v2_over_full": None
                if not pressure_arm["FULL"]["wall_ms"]["p95"]
                else pressure_arm["LATENCY_DEGRADED_V2"]["wall_ms"]["p95"]
                / pressure_arm["FULL"]["wall_ms"]["p95"],
            }
            report["lean"]["engineering_switch"] = switch
            cool(args.cool_s)

        lean_pass = all(s["status"] == "PASS" for s in stages.stages)
        log(f"=== LEAN A-F {'PASS' if lean_pass else 'FAIL'} ===")

        # Soak only after lean PASS
        if args.run_soak and lean_pass:
            log(f"=== V2 SOAK {args.soak_s}s ===")
            soak = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "duration_s_requested": args.soak_s,
                "windows": [],
            }
            v2_rt, _ = bringup_profile(stages, "LATENCY_DEGRADED_V2", crops[0])
            window_s = 15.0
            t_end = time.monotonic() + float(args.soak_s)
            win_id = 0
            all_walls = []
            mem0 = process_snapshot()
            gpu0 = gpu_snapshot()
            soak["process_start"] = mem0
            soak["gpu_start"] = gpu0
            while time.monotonic() < t_end:
                remaining = t_end - time.monotonic()
                dur = min(window_s, remaining)
                if dur < 2:
                    break
                summary, samples = run_window(v2_rt, crops, dur, f"soak_w{win_id}")
                summary["window_id"] = win_id
                summary["elapsed_s"] = round(time.monotonic() - (t_end - float(args.soak_s)), 1)
                soak["windows"].append(summary)
                all_walls.extend(s["wall_ms"] for s in samples)
                log(
                    json.dumps(
                        {
                            "window": win_id,
                            "p95": summary["wall_ms"]["p95"],
                            "rss": summary["process"]["rss_mib"],
                            "temp": summary["gpu"].get("temp_c"),
                            "cls2": summary["cls2_p95"],
                        }
                    )
                )
                win_id += 1
            soak["process_end"] = process_snapshot()
            soak["gpu_end"] = gpu_snapshot()
            soak["global_wall_p50"] = _pct(all_walls, 50)
            soak["global_wall_p95"] = _pct(all_walls, 95)
            last_windows = soak["windows"][-max(1, int(600 / window_s)) :]
            last_p95s = [w["wall_ms"]["p95"] for w in last_windows if w["wall_ms"]["p95"] is not None]
            soak["last_10min_wall_p95_mean"] = _mean(last_p95s)
            soak["exception_count"] = sum(int(w.get("exceptions") or 0) for w in soak["windows"])
            soak["profile_stable"] = all(
                (w.get("identity") or {}).get("classifier_count") == 1 for w in soak["windows"]
            )
            rss0 = mem0.get("rss_mib")
            rss1 = soak["process_end"].get("rss_mib")
            soak["rss_growth_mib"] = None if rss0 is None or rss1 is None else rss1 - rss0
            soak["pass"] = (
                soak["exception_count"] == 0
                and soak["profile_stable"]
                and (soak["rss_growth_mib"] is None or soak["rss_growth_mib"] < 250)
            )
            del v2_rt
            report["soak"] = soak
        elif args.run_soak and not lean_pass:
            log("[SKIP] soak because lean A-F did not PASS")

    except Exception as exc:  # noqa: BLE001
        report["engineering_blocker"] = {
            "type": "exception",
            "error": f"{type(exc).__name__}: {exc}",
            "last_successful_stage": stages.last_successful,
            "traceback": traceback.format_exc()[-3000:],
        }
        lean_pass = False
        log(f"[FAIL] unhandled {report['engineering_blocker']['error']}")

    report["stages"] = stages.stages
    report["lean_pass"] = lean_pass

    # Preserve prior lean pressure results when this invocation skipped pressure
    # (e.g. soak-only follow-up after a successful A–F run).
    prior_path = out_dir / "v2-pressure-pilot-nx.json"
    if args.skip_pressure and prior_path.is_file():
        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            if prior.get("lean") and not report.get("lean"):
                report["lean"] = prior["lean"]
            elif prior.get("lean") and report.get("lean") and not report["lean"].get("pressure"):
                if prior["lean"].get("pressure"):
                    report["lean"]["pressure"] = prior["lean"]["pressure"]
                if prior["lean"].get("engineering_switch"):
                    report["lean"]["engineering_switch"] = prior["lean"]["engineering_switch"]
                if prior["lean"].get("healthy") and not report["lean"].get("healthy"):
                    report["lean"]["healthy"] = prior["lean"]["healthy"]
            if prior.get("previous_run_event"):
                report["previous_run_event"] = prior["previous_run_event"]
            report["prior_lean_merged"] = True
        except Exception as exc:  # noqa: BLE001
            report["prior_lean_merge_error"] = str(exc)

    # Verdict from lean pressure if present
    arms = (report.get("lean") or {}).get("pressure", {}).get("arms") or {}
    fp = (arms.get("FULL") or {}).get("wall_ms", {}).get("p95")
    vp = (arms.get("LATENCY_DEGRADED_V2") or {}).get("wall_ms", {}).get("p95")
    if fp is not None and vp is not None:
        full_above = fp >= ADMISSION_P95_MS
        v2_below = vp < ADMISSION_P95_MS
        v2_mitigates = vp < fp * 0.9
        if full_above and v2_below:
            latency_recovery = "PRELIMINARY SUPPORTED"
            mission_latency_recovery = "PRELIMINARY SUPPORTED"
        elif v2_mitigates and not v2_below:
            latency_recovery = "SUPPORTED"
            mission_latency_recovery = "NOT ESTABLISHED"
        elif v2_mitigates and v2_below and not full_above:
            latency_recovery = "PRELIMINARY SUPPORTED"
            mission_latency_recovery = "INCONCLUSIVE_FULL_NOT_ALWAYS_ABOVE_GATE"
        else:
            latency_recovery = "NOT SUPPORTED UNDER QUALIFIED PRESSURE"
            mission_latency_recovery = "NOT ESTABLISHED"
    else:
        latency_recovery = "NOT EVALUATED"
        mission_latency_recovery = "NOT ESTABLISHED"

    report["verdict"] = {
        "lean_af": "PASS" if lean_pass else "FAIL",
        "full_pressure_p95": fp,
        "v2_pressure_p95": vp,
        "ratio_v2_over_full": None if not fp else (None if vp is None else vp / fp),
        "LATENCY_RECOVERY_MECHANISM": latency_recovery,
        "MISSION_LATENCY_RECOVERY": mission_latency_recovery,
        "ENGINEERING_SOAK": None
        if not report.get("soak")
        else ("PASS" if report["soak"].get("pass") else "FAIL"),
        "A3_EFFECTIVENESS": "NOT ESTABLISHED",
        "FORMAL_QUALITY_ADMISSION": "BLOCKED ON FRESH SCRATCH-ONLY HOLDOUT",
        "ONLY_FORMAL_BLOCKER": "FRESH SCRATCH-ONLY HOLDOUT"
        if lean_pass and not report.get("engineering_blocker")
        else (
            report.get("engineering_blocker") or {}
        ).get("type")
        or "FRESH SCRATCH-ONLY HOLDOUT",
        "previous_run_buffering_vs_hang": "UNDETERMINED",
    }
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    json_path = out_dir / "v2-pressure-pilot-nx.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    log(json.dumps(report["verdict"], indent=2))
    log(f"wrote {json_path}")
    return 0 if lean_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
