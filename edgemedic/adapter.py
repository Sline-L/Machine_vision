"""Snapshot v2 → Agent view. Does not mutate GearPro public schema."""

from __future__ import annotations

import copy


def adapt_snapshot(raw):
    """Accept SystemSnapshot v1/v2 or control-view; hoist specialists for policy."""
    snap = copy.deepcopy(raw or {})
    specialists = snap.get("specialists") or {}
    scratch = snap.get("scratch_v5")
    if not isinstance(scratch, dict):
        scratch = specialists.get("scratch_v5") if isinstance(specialists.get("scratch_v5"), dict) else {}
    missing = snap.get("missing_hole_v1")
    if not isinstance(missing, dict):
        missing = specialists.get("missing_hole_v1") if isinstance(specialists.get("missing_hole_v1"), dict) else {}
    snap["scratch_v5"] = dict(scratch)
    snap["missing_hole_v1"] = dict(missing)
    if "specialists" not in snap:
        snap["specialists"] = {
            "scratch_v5": dict(scratch),
            "missing_hole_v1": dict(missing),
        }
    else:
        snap["specialists"] = dict(specialists)
        snap["specialists"].setdefault("scratch_v5", dict(scratch))
        snap["specialists"].setdefault("missing_hole_v1", dict(missing))
    inference = snap.get("inference")
    if not isinstance(inference, dict):
        snap["inference"] = {
            "unavailable": True,
            "note": "inference block missing from snapshot",
        }
    return snap


def specialist_view(snap):
    """Independent specialist fields for contracts and Verify evidence."""
    snap = adapt_snapshot(snap)
    scratch = snap.get("scratch_v5") or {}
    missing = snap.get("missing_hole_v1") or {}
    return {
        "scratch_v5": {
            "loaded": scratch.get("loaded"),
            "load_status": scratch.get("load_status"),
            "health": scratch.get("health"),
            "total_latency_ms": scratch.get("total_latency_ms"),
            "error_count": scratch.get("error_count"),
            "last_error": scratch.get("last_error"),
        },
        "missing_hole_v1": {
            "loaded": missing.get("loaded"),
            "load_status": missing.get("load_status"),
            "health": missing.get("health"),
            "total_latency_ms": missing.get("total_latency_ms"),
            "error_count": missing.get("error_count"),
            "last_error": missing.get("last_error"),
        },
        "camera": {
            "opened": (snap.get("camera") or {}).get("opened"),
            "frame_seq": (snap.get("camera") or {}).get("frame_seq"),
            "frame_age_ms": (snap.get("camera") or {}).get("frame_age_ms"),
            "health": (snap.get("camera") or {}).get("health"),
        },
        "mission": {
            "inspection_active": (snap.get("mission") or {}).get("inspection_active"),
            "current_profile": (snap.get("mission") or {}).get("current_profile"),
            "inspection_count": (snap.get("mission") or {}).get("inspection_count"),
            "emergency_hold": (snap.get("mission") or {}).get("emergency_hold"),
        },
        "system": {
            "temperature_c": (snap.get("system") or {}).get("temperature_c"),
        },
        "schema_version": snap.get("schema_version"),
        "timestamp": snap.get("timestamp"),
    }
