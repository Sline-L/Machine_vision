"""Record which runtime, bundle, and reasoner produced an experiment file."""

from pathlib import Path
import hashlib
import json
import subprocess
import time


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "model" / "model2" / "manifest.json"


def git_head(cwd=None):
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd or REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or "").strip() or None


def _manifest():
    if not MANIFEST_PATH.is_file():
        return None, None, None
    raw = MANIFEST_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, digest, None
    return payload.get("bundle_id"), digest, payload


def collect_provenance(reasoner="mock", runtime_mode="synthetic", snapshot=None):
    """Monorepo: runtime_commit and agent_commit are the same HEAD until split."""
    commit = git_head()
    bundle_id, manifest_sha256, manifest = _manifest()
    mode = runtime_mode
    if snapshot:
        device = ((snapshot.get("camera") or {}).get("device") or "")
        if str(device).startswith("replay:"):
            mode = "dataset_replay"
        elif snapshot.get("source_type") == "replay":
            mode = "dataset_replay"
    return {
        "runtime_commit": commit,
        "agent_commit": commit,
        "bundle_id": bundle_id,
        "manifest_sha256": manifest_sha256,
        "reasoner": "qwen3-4b" if reasoner == "qwen" else reasoner,
        "runtime_mode": mode,
        "manifest_path": None if not MANIFEST_PATH.is_file() else str(MANIFEST_PATH),
        "model_family": None if not manifest else manifest.get("model_family"),
    }


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


def summarize_samples(samples):
    samples = list(samples or [])
    valid = [item for item in samples if item.get("output_valid")]
    loc = [item.get("locator_latency_ms") for item in valid]
    v5 = [item.get("v5_latency_ms") for item in valid]
    totals = []
    for item in valid:
        loc_ms = item.get("locator_latency_ms")
        v5_ms = item.get("v5_latency_ms")
        if loc_ms is None or v5_ms is None:
            continue
        totals.append(float(loc_ms) + float(v5_ms))
    last = samples[-1] if samples else {}
    return {
        "cycle_count": len(samples),
        "valid_ratio": None if not samples else round(len(valid) / len(samples), 4),
        "locator": {"p50": _percentile(loc, 50), "p95": _percentile(loc, 95)},
        "scratch_v5": {"p50": _percentile(v5, 50), "p95": _percentile(v5, 95)},
        "total": {"p50": _percentile(totals, 50), "p95": _percentile(totals, 95)},
        "gpu_util": last.get("gpu_util"),
        "gpu_mem_mb": last.get("gpu_mem_mb"),
        "ram_used_mb": last.get("ram_used_mb"),
        "temperature_c": last.get("temperature_c"),
        "power_w": last.get("power_w"),
        "profile": last.get("profile"),
        "locator_backend": last.get("locator_backend"),
        "utility": last.get("utility"),
        "experimentally_validated": False,
    }


def sample_live(url, duration_s=20.0, interval=0.5):
    from edgemedic.client import ControlClient

    client = ControlClient(url)
    samples = []
    deadline = time.monotonic() + max(0.1, float(duration_s))
    snapshot = None
    while time.monotonic() <= deadline:
        snapshot = client.get_state()
        samples.append(snapshot_telem(snapshot))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(float(interval), remaining))
    return {
        "control_url": url,
        "samples": samples,
        "summary": summarize_samples(samples),
        "provenance": collect_provenance(runtime_mode="dataset_replay", snapshot=snapshot),
    }


def live_action(url, name, params, source="reasoner"):
    from edgemedic.client import ControlClient

    client = ControlClient(url)
    result = client.post_action(name, params=params or {}, source=source, request_id=f"stage-c-{name}")
    return {
        "name": name,
        "params": params or {},
        "verify_level": result.get("verify_level"),
        "accepted": result.get("accepted"),
        "executed": result.get("executed"),
        "error": result.get("error"),
        "recovery_success": result.get("recovery_success"),
        "experimentally_validated": False,
    }


def snapshot_telem(snapshot):
    system = snapshot.get("system") or {}
    locator = snapshot.get("locator") or {}
    v5 = snapshot.get("scratch_v5") or {}
    mission = snapshot.get("mission") or {}
    return {
        "gpu_util": system.get("gpu_util"),
        "gpu_mem_mb": system.get("gpu_mem_mb"),
        "ram_used_mb": system.get("ram_used_mb"),
        "temperature_c": system.get("temperature_c"),
        "power_w": system.get("power_w"),
        "locator_backend": locator.get("backend"),
        "locator_latency_ms": locator.get("latency_ms"),
        "v5_latency_ms": v5.get("total_latency_ms"),
        "profile": v5.get("profile") or mission.get("current_profile"),
        "output_valid": mission.get("output_valid"),
        "utility": mission.get("utility"),
        "inspection_active": mission.get("inspection_active"),
    }
