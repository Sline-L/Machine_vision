"""Named inference profiles that humans and EdgeMedic both use."""

from pathlib import Path

from .config import PROJECT_ROOT

PT_LOCATOR = PROJECT_ROOT / "model" / "model1.pt"
ENGINE_LOCATOR = PROJECT_ROOT / ".cache" / "exports" / "model1.engine"

IMPLEMENTED = ("FULL", "SPARSE", "SAFE_STOP", "TRT_FAST")

SPECS = {
    "FULL": {
        "inference_interval": 0.10,
        "mission_quality": 1.00,
        "stop_worker": False,
        "implemented": True,
        "locator": "pt",
    },
    "SPARSE": {
        "inference_interval": 0.20,
        "mission_quality": 0.90,
        "stop_worker": False,
        "implemented": True,
        "locator": "keep",
    },
    "SAFE_STOP": {
        "inference_interval": None,
        "mission_quality": 0.00,
        "stop_worker": True,
        "implemented": True,
        "locator": "keep",
    },
    "TRT_FAST": {
        "inference_interval": 0.10,
        "mission_quality": 1.00,
        "stop_worker": False,
        "implemented": True,
        "locator": "engine",
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


def spec(name):
    profile = SPECS.get(name)
    if profile is None:
        raise ProfileError(f"未知档位：{name}")
    return profile


def _same_path(left, right):
    return Path(left).resolve() == Path(right).resolve()


def apply_to_config(config, name):
    profile = spec(name)
    if not profile.get("implemented"):
        raise ProfileError(f"档位 {name} 尚未实现")
    previous = getattr(config, "inference_profile", "FULL")
    previous_locator = Path(config.locator_model)
    rebuild = False
    locator_kind = profile.get("locator")
    if locator_kind == "engine":
        if not ENGINE_LOCATOR.is_file():
            raise ProfileError("找不到 model1.engine，无法进入 TRT_FAST")
        config.locator_model = ENGINE_LOCATOR
        rebuild = not _same_path(previous_locator, ENGINE_LOCATOR)
    elif locator_kind == "pt":
        if previous == "TRT_FAST" and PT_LOCATOR.is_file():
            config.locator_model = PT_LOCATOR
            rebuild = not _same_path(previous_locator, PT_LOCATOR)
    config.inference_profile = name
    if profile.get("inference_interval") is not None:
        config.inference_interval = float(profile["inference_interval"])
    return {
        "previous": previous,
        "previous_locator": str(previous_locator),
        "stop_worker": bool(profile.get("stop_worker")),
        "start_worker": name != "SAFE_STOP" and previous == "SAFE_STOP",
        "rebuild_inspector": rebuild,
    }


def locator_path_for(name):
    path = LOCATOR_PROFILES.get(name)
    if path is None:
        raise ProfileError(f"未知定位档位：{name}")
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
