"""In-process Hard Guardian. EdgeMedic still runs as a separate process over HTTP.

80°C is an EdgeMedic/GearPro operational policy threshold, not a Jetson hardware
absolute limit. Hard Guardian may only reduce capability (e.g. FULL → SAFE_STOP)
and never autonomously raise it.
"""

THERMAL_POLICY_C = 80.0
THERMAL_STOP_C = THERMAL_POLICY_C


def thermal_alarm(snapshot):
    temp = (snapshot.get("system") or {}).get("temperature_c")
    if temp is None:
        return False
    return float(temp) >= THERMAL_STOP_C


def thermal_stop_needed(snapshot, current_profile):
    return thermal_alarm(snapshot) and current_profile != "SAFE_STOP"
