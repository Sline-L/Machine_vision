"""Named inference profiles that humans and EdgeMedic both use."""

IMPLEMENTED = ("FULL", "SPARSE", "SAFE_STOP")

SPECS = {
    "FULL": {
        "inference_interval": 0.10,
        "mission_quality": 1.00,
        "stop_worker": False,
        "implemented": True,
    },
    "SPARSE": {
        "inference_interval": 0.20,
        "mission_quality": 0.90,
        "stop_worker": False,
        "implemented": True,
    },
    "SAFE_STOP": {
        "inference_interval": None,
        "mission_quality": 0.00,
        "stop_worker": True,
        "implemented": True,
    },
    "TRT_FAST": {"implemented": False, "mission_quality": 1.00},
    "CLASSIFY_ONLY": {"implemented": False, "mission_quality": 0.65},
    "LOCATE_ONLY": {"implemented": False, "mission_quality": 0.20},
}


class ProfileError(ValueError):
    pass


def spec(name):
    profile = SPECS.get(name)
    if profile is None:
        raise ProfileError(f"未知档位：{name}")
    return profile


def apply_to_config(config, name):
    profile = spec(name)
    if not profile.get("implemented"):
        raise ProfileError(f"档位 {name} 尚未实现")
    previous = getattr(config, "inference_profile", "FULL")
    config.inference_profile = name
    if profile.get("inference_interval") is not None:
        config.inference_interval = float(profile["inference_interval"])
    return {
        "previous": previous,
        "stop_worker": bool(profile.get("stop_worker")),
        "start_worker": name != "SAFE_STOP" and previous == "SAFE_STOP",
    }


def mission_utility(profile_name, locator_ok, serial_ok):
    profile = SPECS.get(profile_name)
    if profile is None or not profile.get("implemented"):
        return None
    quality = float(profile["mission_quality"])
    locator = 1.0 if locator_ok else 0.0
    serial = 1.0 if serial_ok else 0.0
    return round(0.3 * locator + 0.5 * quality + 0.2 * serial, 4)
