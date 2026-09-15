"""Named inference profiles that humans and EdgeMedic both use."""

from pathlib import Path
import hashlib
import json

from .capability_registry import CapabilityError, assert_switchable, list_profile_availability
from .capability_v2 import (
    FULL_INFERENCE_CONFIG,
    PROFILE_ID as LATENCY_DEGRADED_V2,
    V2_INFERENCE_CONFIG,
    validate_frozen_artifacts,
    CapabilityArtifactError,
)
from .config import PROJECT_ROOT

PT_LOCATOR = PROJECT_ROOT / "model" / "model1.pt"
ENGINE_LOCATOR = PROJECT_ROOT / "model" / "model1" / "model1.engine"
ENGINE_MANIFEST = PROJECT_ROOT / "model" / "model1" / "manifest.json"

IMPLEMENTED = ("FULL", "SPARSE", "SAFE_STOP", "TRT_FAST", "LATENCY_DEGRADED_V2")

SPECS = {
    "FULL": {
        "inference_interval": 0.10,
        "mission_quality": 1.00,
        "stop_worker": False,
        "implemented": True,
        "locator": "pt",
        "scratch_bundle": "full",
    },
    "SPARSE": {
        "inference_interval": 0.20,
        "mission_quality": 0.90,
        "stop_worker": False,
        "implemented": True,
        "locator": "keep",
        "scratch_bundle": "keep",
    },
    "SAFE_STOP": {
        "inference_interval": None,
        "mission_quality": 0.00,
        "stop_worker": True,
        "implemented": True,
        "locator": "keep",
        "scratch_bundle": "keep",
    },
    "TRT_FAST": {
        "inference_interval": 0.10,
        "mission_quality": 1.00,
        "stop_worker": False,
        "implemented": True,
        "locator": "engine",
        "scratch_bundle": "keep",
    },
    "LATENCY_DEGRADED_V2": {
        "inference_interval": 0.10,
        # Provisional ceiling from exploratory val Q_D; not a formal Mission guarantee.
        "mission_quality": 0.8879,
        "stop_worker": False,
        "implemented": True,
        "locator": "keep",
        "scratch_bundle": "latency_degraded_v2",
        "applicability": ["V5_OVERLOAD"],
    },
    "CLASSIFY_ONLY": {"implemented": False, "mission_quality": 0.65},
    "LOCATE_ONLY": {"implemented": False, "mission_quality": 0.20},
}

LOCATOR_PROFILES = {
    "pt_safe": PT_LOCATOR,
    "trt_fast": ENGINE_LOCATOR,
}


class ProfileError(ValueError):
    pass


def load_engine_manifest():
    if not ENGINE_MANIFEST.is_file():
        return None
    payload = json.loads(ENGINE_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProfileError("locator engine manifest 必须是对象")
    return payload


def verify_engine_artifact():
    if not ENGINE_LOCATOR.is_file():
        raise ProfileError(f"找不到 model1.engine：{ENGINE_LOCATOR}")
    manifest = load_engine_manifest()
    if manifest is None:
        raise ProfileError(f"缺少 engine provenance：{ENGINE_MANIFEST}")
    listed = str((manifest.get("engine") or {}).get("sha256") or "").lower()
    actual = hashlib.sha256(ENGINE_LOCATOR.read_bytes()).hexdigest()
    if listed and listed != actual:
        raise ProfileError("model1.engine SHA256 与 manifest 不一致")
    return manifest


def spec(name):
    profile = SPECS.get(name)
    if profile is None:
        raise ProfileError(f"未知档位：{name}")
    return profile


def _same_path(left, right):
    return Path(left).resolve() == Path(right).resolve()


def _apply_scratch_bundle(config, bundle_kind, previous_model2):
    """Switch Scratch V5 topology. Returns (rebuild_needed, previous_threshold)."""
    previous_threshold = float(config.defect_threshold)
    rebuild = False
    if bundle_kind == "latency_degraded_v2":
        try:
            identity = validate_frozen_artifacts()
        except CapabilityArtifactError as exc:
            raise ProfileError(f"{exc.reason}: {exc}") from exc
        target = V2_INFERENCE_CONFIG
        if not target.is_file():
            raise ProfileError(f"CAPABILITY_ARTIFACT_MISSING: {target}")
        rebuild = not _same_path(previous_model2, target)
        config.model2_config = target
        config.defect_threshold = float(identity["threshold"])
    elif bundle_kind == "full":
        target = FULL_INFERENCE_CONFIG
        if not target.is_file():
            raise ProfileError(f"找不到 FULL Scratch 配置：{target}")
        rebuild = not _same_path(previous_model2, target)
        config.model2_config = target
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            config.defect_threshold = float(payload["default_threshold"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProfileError(f"无法读取 FULL Scratch 阈值：{exc}") from exc
    return rebuild, previous_threshold


def apply_to_config(config, name, *, engineering_mode=False):
    profile = spec(name)
    if not profile.get("implemented"):
        raise ProfileError(f"档位 {name} 尚未实现")
    try:
        assert_switchable(name, legacy_implemented=True, engineering_mode=engineering_mode)
    except CapabilityError as exc:
        raise ProfileError(str(exc)) from exc
    previous = getattr(config, "inference_profile", "FULL")
    previous_locator = Path(config.locator_model)
    previous_model2 = Path(config.model2_config)
    previous_threshold = float(config.defect_threshold)
    rebuild = False
    locator_kind = profile.get("locator")
    if locator_kind == "engine":
        verify_engine_artifact()
        config.locator_model = ENGINE_LOCATOR
        rebuild = not _same_path(previous_locator, ENGINE_LOCATOR)
    elif locator_kind == "pt":
        if previous == "TRT_FAST" and PT_LOCATOR.is_file():
            config.locator_model = PT_LOCATOR
            rebuild = not _same_path(previous_locator, PT_LOCATOR)
    scratch_kind = profile.get("scratch_bundle", "keep")
    scratch_rebuild = False
    if scratch_kind in {"full", "latency_degraded_v2"}:
        scratch_rebuild, _ = _apply_scratch_bundle(config, scratch_kind, previous_model2)
        rebuild = rebuild or scratch_rebuild
    elif scratch_kind == "keep":
        # Cadence/locator overlays must not retain a degraded Scratch topology.
        if previous_model2.resolve() == V2_INFERENCE_CONFIG.resolve():
            scratch_rebuild, _ = _apply_scratch_bundle(config, "full", previous_model2)
            rebuild = rebuild or scratch_rebuild
    config.inference_profile = name
    if profile.get("inference_interval") is not None:
        config.inference_interval = float(profile["inference_interval"])
    return {
        "previous": previous,
        "previous_locator": str(previous_locator),
        "previous_model2": str(previous_model2),
        "previous_threshold": previous_threshold,
        "stop_worker": bool(profile.get("stop_worker")),
        "start_worker": name != "SAFE_STOP" and previous == "SAFE_STOP",
        "rebuild_inspector": rebuild,
        "engineering_mode": bool(engineering_mode),
        "scratch_bundle": scratch_kind,
    }


def available_capabilities():
    """Read-only availability for Control/Agent (fail-closed registry)."""
    return list_profile_availability(SPECS)


def locator_path_for(name):
    path = LOCATOR_PROFILES.get(name)
    if path is None:
        raise ProfileError(f"未知定位档位：{name}")
    if name == "trt_fast":
        verify_engine_artifact()
    if not path.is_file():
        raise ProfileError(f"找不到定位权重：{path}")
    return path


def mission_utility(profile_name, locator_ok, serial_ok, valid_output_ratio=None, latency_score=None):
    profile = SPECS.get(profile_name)
    if profile is None or not profile.get("implemented"):
        return None
    ceiling = float(profile["mission_quality"])
    q_l = 1.0 if locator_ok else 0.0
    if latency_score is not None:
        q_l *= max(0.0, min(1.0, float(latency_score)))
    ratio = 1.0 if valid_output_ratio is None else max(0.0, min(1.0, float(valid_output_ratio)))
    q_d = ratio * ceiling
    q_s = 1.0 if serial_ok else 0.0
    return round(0.3 * q_l + 0.5 * q_d + 0.2 * q_s, 4)


def profile_applicable(name, fault_code):
    """Future A3 applicability plumbing (not an auto-enable)."""
    profile = SPECS.get(name) or {}
    allowed = profile.get("applicability")
    if not allowed:
        return True
    return fault_code in allowed
