"""Jetson-oriented telemetry. Snapshot consumes this; backends stay swappable."""

from pathlib import Path
import glob


def _read_number(path):
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def _first_number(paths):
    for path in paths:
        value = _read_number(path)
        if value is not None:
            return value
    return None


def _gpu_util_percent():
    candidates = []
    candidates.extend(sorted(glob.glob("/sys/devices/gpu.*/load")))
    candidates.extend(sorted(glob.glob("/sys/devices/platform/*.gpu/load")))
    candidates.extend(sorted(glob.glob("/sys/devices/platform/*/*.gpu/load")))
    candidates.extend(sorted(glob.glob("/sys/class/devfreq/*/load")))
    raw = _first_number(candidates)
    if raw is None:
        return None
    if raw > 100.0:
        return max(0.0, min(100.0, raw / 10.0))
    return max(0.0, min(100.0, raw))


def _gpu_mem_mb():
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return None
    try:
        lines = meminfo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    values = {}
    for line in lines:
        parts = line.replace(":", " ").split()
        if len(parts) >= 2:
            values[parts[0]] = float(parts[1])
    used_kb = values.get("NvMapMemUsed") or values.get("NvmallocUsed")
    if used_kb is None:
        return None
    return used_kb / 1024.0


def _power_w():
    for power_path in sorted(glob.glob("/sys/class/hwmon/hwmon*/power*_input")):
        raw = _read_number(power_path)
        if raw is not None and raw > 0:
            if raw > 1000:
                return raw / 1_000_000.0
            return raw
    names = sorted(glob.glob("/sys/class/hwmon/hwmon*/name"))
    for name_path in names:
        try:
            name = Path(name_path).read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if "ina" not in name and "power" not in name:
            continue
        hwmon = Path(name_path).parent
        voltage = _first_number(sorted(str(p) for p in hwmon.glob("in*_input")))
        current = _first_number(sorted(str(p) for p in hwmon.glob("curr*_input")))
        if voltage is not None and current is not None:
            watts = (voltage / 1000.0) * (current / 1000.0)
            if watts > 0:
                return watts
    return None


def _temperature_c():
    zones = sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp"))
    readings = []
    for path in zones:
        raw = _read_number(path)
        if raw is None:
            continue
        temp = raw / 1000.0 if raw > 200 else raw
        if 0.0 < temp < 150.0:
            readings.append(temp)
    if not readings:
        return None
    return max(readings)


def read_jetson_metrics():
    """Fill GPU/power/temp when the platform exposes them. Unknown stays null."""
    return {
        "gpu_util": _gpu_util_percent(),
        "gpu_mem_mb": _gpu_mem_mb(),
        "power_w": _power_w(),
        "temperature_c": _temperature_c(),
    }
