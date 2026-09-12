"""In-process L0 checks. EdgeMedic still runs as a separate process over HTTP."""

THERMAL_STOP_C = 80.0


def thermal_stop_needed(snapshot, current_profile):
    temp = (snapshot.get("system") or {}).get("temperature_c")
    if temp is None:
        return False
    return float(temp) >= THERMAL_STOP_C and current_profile != "SAFE_STOP"
