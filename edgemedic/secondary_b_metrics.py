"""Secondary B continuity metrics: intentional skip vs pressure miss.

Profile cadence (interval) is intentional shedding — not overload failure.
"""

from __future__ import annotations


def percentile(values, pct):
    ordered = sorted(float(v) for v in values if v is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def summarize_ages(ages_ms):
    return {
        "n": len([a for a in ages_ms if a is not None]),
        "p50": round(percentile(ages_ms, 50), 3) if ages_ms else None,
        "p95": round(percentile(ages_ms, 95), 3) if ages_ms else None,
        "max": round(max(ages_ms), 3) if ages_ms else None,
        "mean": round(sum(ages_ms) / len(ages_ms), 3) if ages_ms else None,
    }


def account_demand_opportunities(
    demand_times,
    inspect_events,
    interval_s,
):
    """Classify each external demand tick vs profile-aware eligibility.

    inspect_events: list of dicts with keys start, end, valid (monotonic times).

    intentional_skip: demand arrives while worker is still gated by cadence
      (before next eligible start = last_inspect_end + interval), OR during an
      in-flight inspect that started on schedule — counted as deliberate non-service
      of surplus demand under LatestFrame+interval semantics when the worker is
      busy/gated as designed.

    pressure_miss: demand arrives when worker is eligible (idle past interval)
      but no valid inspection completes that covers the demand before the next
      eligible window closes without service — approximated as: eligible demand
      with no inspect start within a short grace after eligibility.

    For LatestFrame single-worker, surplus demand during busy/gated time is
    primarily intentional relative to cadence; true pressure_miss focuses on
    eligible slots that fail to produce a valid completion.
    """
    interval_s = float(interval_s)
    inspects = sorted(inspect_events, key=lambda e: float(e["start"]))
    intentional = 0
    pressure_miss = 0
    eligible = 0
    served_eligible = 0

    # Build eligible windows: after each inspect end + interval, until next inspect start
    # Also initial eligibility from t0.
    for t in demand_times:
        t = float(t)
        # Find last inspect that ended before t
        last_end = None
        in_flight = False
        for ev in inspects:
            if float(ev["start"]) <= t < float(ev["end"]):
                in_flight = True
                break
            if float(ev["end"]) <= t:
                last_end = float(ev["end"])
            elif float(ev["start"]) > t:
                break

        if in_flight:
            intentional += 1
            continue

        if last_end is None:
            # Before first inspect: treat as eligible if any inspect starts soon
            eligible += 1
            started = any(abs(float(ev["start"]) - t) < interval_s for ev in inspects)
            if started:
                served_eligible += 1
            else:
                # No inspect yet covering early demand — count miss only if later
                # we never get an inspect (handled loosely as intentional warm-up skip)
                intentional += 1
                eligible -= 1
            continue

        gated_until = last_end + interval_s
        if t < gated_until:
            intentional += 1
            continue

        # Eligible under profile cadence
        eligible += 1
        # Served if an inspect starts within [gated_until, gated_until + interval) after this demand
        # or an inspect starts at/after t before next gate
        served = False
        for ev in inspects:
            if float(ev["start"]) >= t and float(ev["start"]) <= t + interval_s + 0.05:
                if ev.get("valid", True):
                    served = True
                    break
        if served:
            served_eligible += 1
        else:
            pressure_miss += 1

    n_demand = len(demand_times)
    n_completed = sum(1 for ev in inspects if ev.get("valid", True))
    return {
        "n_demand": n_demand,
        "n_completed": n_completed,
        "raw_opportunity_deficit": max(0, n_demand - n_completed),
        "intentional_skip": intentional,
        "eligible_opportunity_count": eligible,
        "pressure_miss": pressure_miss,
        "served_eligible": served_eligible,
        "intentional_skip_rate": (intentional / n_demand) if n_demand else None,
        "pressure_miss_rate": (pressure_miss / eligible) if eligible else None,
    }
