"""Record which runtime, bundle, reasoner, and fault evidence class produced a run."""

from pathlib import Path
import hashlib
import json
import subprocess
import time


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "model" / "model2" / "manifest.json"
LOCATOR_ENGINE_MANIFEST = REPO_ROOT / "model" / "model1" / "manifest.json"

# Do not mix these in one results table.
FAULT_NONE = "none"
FAULT_SYNTHETIC_SNAPSHOT = "synthetic_snapshot"
FAULT_REAL_RESOURCE_PRESSURE = "real_resource_pressure"
FAULT_MODES = (FAULT_NONE, FAULT_SYNTHETIC_SNAPSHOT, FAULT_REAL_RESOURCE_PRESSURE)


def experiment_config_hash(config):
    raw = json.dumps(config or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _locator_engine_fields():
    if not LOCATOR_ENGINE_MANIFEST.is_file():
        return {"locator_engine_id": None, "locator_engine_sha256": None}
    try:
        payload = json.loads(LOCATOR_ENGINE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"locator_engine_id": None, "locator_engine_sha256": None}
    engine = payload.get("engine") or {}
    return {
        "locator_engine_id": payload.get("artifact_id"),
        "locator_engine_sha256": engine.get("sha256"),
        "locator_engine_path": engine.get("path"),
    }


def _replay_pack_fields(pack_dir):
    if not pack_dir:
        return {"replay_pack_id": None, "replay_pack_hash": None}
    path = Path(pack_dir)
    manifest_path = path / "replay_manifest.json"
    if not manifest_path.is_file():
        return {"replay_pack_id": None, "replay_pack_hash": None}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"replay_pack_id": None, "replay_pack_hash": None}
    body = {
        "replay_pack_id": manifest.get("replay_pack_id"),
        "source_repo": manifest.get("source_repo"),
        "source_commit": manifest.get("source_commit"),
        "locked_test": manifest.get("locked_test"),
        "files": manifest.get("files") or [],
    }
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "replay_pack_id": manifest.get("replay_pack_id"),
        "replay_pack_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "replay_locked_test": manifest.get("locked_test"),
        "replay_sample_count": manifest.get("sample_count"),
    }


def collect_provenance(
    reasoner="mock",
    runtime_mode="synthetic",
    snapshot=None,
    fault_mode=FAULT_NONE,
    experiment_config=None,
    replay_pack_dir=None,
    llm_url=None,
):
    """Monorepo: runtime_commit and agent_commit are the same HEAD until split."""
    if fault_mode not in FAULT_MODES:
        raise ValueError(f"未知 fault_mode：{fault_mode}")
    commit = git_head()
    bundle_id, manifest_sha256, manifest = _manifest()
    mode = runtime_mode
    if snapshot:
        device = ((snapshot.get("camera") or {}).get("device") or "")
        if str(device).startswith("replay:"):
            mode = "dataset_replay"
        elif snapshot.get("source_type") == "replay":
            mode = "dataset_replay"
    config = dict(experiment_config or {})
    replay_dir = replay_pack_dir or config.get("replay_pack_dir")
    payload = {
        "runtime_commit": commit,
        "agent_commit": commit,
        "bundle_id": bundle_id,
        "manifest_sha256": manifest_sha256,
        "reasoner": "qwen3-4b" if reasoner == "qwen" else reasoner,
        "runtime_mode": mode,
        "fault_mode": fault_mode,
        "experiment_config": config,
        "experiment_config_hash": experiment_config_hash(config),
        "manifest_path": None if not MANIFEST_PATH.is_file() else str(MANIFEST_PATH),
        "model_family": None if not manifest else manifest.get("model_family"),
    }
    payload.update(_locator_engine_fields())
    payload.update(_replay_pack_fields(replay_dir))
    for key in (
        "fault_injector_type",
        "fault_injector_config",
        "fault_injector_hash",
        "fault_injector_version",
        "recovery_strategy",
    ):
        if key in config:
            payload[key] = config[key]
    if llm_url:
        payload.update(_llm_fields(llm_url, config))
    return payload


def _llm_fields(llm_url, config):
    from edgemedic.reasoner import ACTION_GBNF_SHA256, llama_server_props

    props = llama_server_props(llm_url)
    health = props.get("/health") or {}
    models = props.get("/v1/models") or {}
    server = props.get("/props") or {}
    model_id = None
    data = models.get("data") if isinstance(models, dict) else None
    if isinstance(data, list) and data:
        model_id = (data[0] or {}).get("id")
    model_path = server.get("model_path")
    gguf_sha = None
    if model_path and Path(model_path).is_file():
        digest = hashlib.sha256()
        with open(model_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        gguf_sha = digest.hexdigest()
    return {
        "llm_url": llm_url,
        "llama_health": health,
        "llama_build": server.get("build_info"),
        "llama_props": {key: server.get(key) for key in ("total_slots", "build_info", "model_alias", "model_path") if key in server},
        "gguf_model_id": model_id,
        "gguf_sha256": gguf_sha,
        "grammar_sha256": config.get("grammar_sha256") or (ACTION_GBNF_SHA256 if config.get("decode") == "grammar" else None),
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


def sample_live(url, duration_s=20.0, interval=0.5, fault_mode=FAULT_NONE, experiment_config=None, reasoner="mock"):
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
        "provenance": collect_provenance(
            reasoner=reasoner,
            runtime_mode="dataset_replay",
            snapshot=snapshot,
            fault_mode=fault_mode,
            experiment_config=experiment_config,
        ),
    }


def live_action(url, name, params, source="reasoner"):
    from edgemedic.client import ControlClient

    client = ControlClient(url, timeout=120.0)
    result = client.post_action(name, params=params or {}, source=source, request_id=f"stage-c-{name}", timeout=120.0)
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
        "profile": mission.get("current_profile") or v5.get("profile"),
        "output_valid": mission.get("output_valid"),
        "utility": mission.get("utility"),
        "inspection_active": mission.get("inspection_active"),
    }
