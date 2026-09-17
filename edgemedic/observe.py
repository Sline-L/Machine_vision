"""Observe-only Agent diagnose: L0 → L1 → MEM → (optional historical L2). Never executes."""

from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path

from .incident import build_incident
from .memory import EpisodeStore
from .policy import Memory, classify_fault, decide

EXECUTION_MODE = "observe_only"


def normalize_snapshot(raw):
    """Accept v1 or v2-shaped health; expose top-level scratch_v5 for L1 rules."""
    snap = copy.deepcopy(raw or {})
    specialists = snap.get("specialists") or {}
    if "scratch_v5" not in snap and specialists.get("scratch_v5"):
        snap["scratch_v5"] = dict(specialists["scratch_v5"])
    if "missing_hole_v1" not in snap and specialists.get("missing_hole_v1"):
        snap["missing_hole_v1"] = dict(specialists["missing_hole_v1"])
    return snap


def _layers_trace(fault, l1_action, mem_hit, l2_record):
    selected = None
    if l1_action is not None:
        selected = l1_action.get("layer") or "L1"
    elif mem_hit is not None:
        selected = "MEM"
    elif l2_record is not None:
        selected = "L2"
    return {
        "L0": "checked" if fault == "THERMAL_STOP" or (l1_action and l1_action.get("layer") == "L0") else "idle",
        "L1": "selected" if selected == "L1" or selected == "L0" else ("candidate" if l1_action else "idle"),
        "MEM": "selected" if selected == "MEM" else ("hit" if mem_hit else "miss"),
        "L2": "historical" if l2_record and selected == "L2" else ("skipped" if selected in ("L0", "L1", "MEM") else "not_invoked"),
        "selected": selected,
    }


def diagnose(
    snapshot,
    *,
    store=None,
    memory=None,
    enable_memory=True,
    historical_l2=None,
    live_l2_proposal=None,
    live_l2_meta=None,
    input_source="SYNTHETIC",
    scenario=None,
):
    """Return a diagnosis report. Does not call Control writes or mutate Runtime.

    Optional live_l2_proposal is a pre-fetched {tool/name, params} from a caller that
    already talked to the LLM. This module never opens HTTP to llama-server itself.
    """
    started = time.perf_counter()
    snap = normalize_snapshot(snapshot)
    loop = memory if memory is not None else Memory()
    # Only reset cooldown when the caller did not supply a Memory instance.
    if memory is None:
        loop.last_fire.clear()
    fault = classify_fault(snap, loop)
    l1 = decide(snap, loop)
    mem_suggestion = None
    if enable_memory and store is not None and fault and l1 is None:
        mem_suggestion = store.suggest(fault)
        if mem_suggestion is not None:
            mem_suggestion = {
                **mem_suggestion,
                "source": "memory",
                "layer": "MEM",
                "rule": fault,
                "request_id": f"MEM-{fault}-{uuid.uuid4().hex[:8]}",
            }

    proposed = l1 or mem_suggestion
    l2_used = False
    l2_live = False
    l2_note = None
    if proposed is None and live_l2_proposal and fault:
        tool = live_l2_proposal.get("tool") or live_l2_proposal.get("name")
        if tool:
            proposed = {
                "name": tool,
                "params": live_l2_proposal.get("params") or {},
                "source": "reasoner",
                "layer": "L2",
                "rule": fault,
                "request_id": f"L2-LIVE-{uuid.uuid4().hex[:8]}",
            }
            l2_live = True
            l2_note = (live_l2_meta or {}).get("note") or "LIVE INFERENCE (proposal only; not executed)"
    elif proposed is None and historical_l2 is not None and fault:
        proposed = {
            "name": historical_l2.get("tool") or historical_l2.get("name"),
            "params": historical_l2.get("params") or {},
            "source": "reasoner",
            "layer": "L2",
            "rule": fault,
            "request_id": f"L2-HIST-{uuid.uuid4().hex[:8]}",
        }
        l2_used = True
        l2_note = historical_l2.get("note") or "HISTORICAL REPLAY of frozen L2 proposal; not LIVE INFERENCE"

    incident = None
    if fault or proposed:
        incident = build_incident(
            fault,
            snap,
            proposed,
            (proposed or {}).get("layer"),
            confidence=0.8 if (proposed or {}).get("layer") == "MEM" else 1.0,
        )

    route = _layers_trace(
        fault,
        l1,
        mem_suggestion,
        proposed if (l2_used or l2_live) and proposed and proposed.get("layer") == "L2" else None,
    )
    if l2_live:
        route["L2"] = "live"
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
    specialists = {
        "scratch_v5": (snap.get("scratch_v5") or {}),
        "missing_hole_v1": (snap.get("missing_hole_v1") or (snap.get("specialists") or {}).get("missing_hole_v1") or {}),
    }
    report = {
        "scenario": scenario,
        "input_source": input_source,
        "fault": fault,
        "diagnosis": None if incident is None else incident.get("diagnosis"),
        "route": route,
        "proposed_action": None
        if proposed is None
        else {
            "name": proposed.get("name"),
            "params": proposed.get("params") or {},
            "layer": proposed.get("layer"),
            "rule": proposed.get("rule") or fault,
            "source": proposed.get("source"),
        },
        "authority_decision": {
            "note": "observe-only midterm demo does not submit to Authority/Control",
            "would_require_control_accept": proposed is not None,
            "human_only_blocked": (proposed or {}).get("name")
            in ("apply_settings", "use_camera", "use_video", "reset_stats"),
        },
        "execution_mode": EXECUTION_MODE,
        "actually_executed": False,
        "ACTUAL_EXECUTION_DISABLED": True,
        "recovery_claimed": False,
        "l2": {
            "invoked_live": l2_live,
            "used_historical": l2_used,
            "note": l2_note,
            "meta": live_l2_meta,
        },
        "evidence": None if incident is None else incident.get("evidence"),
        "system_view": {
            "camera": snap.get("camera") or {},
            "mission": snap.get("mission") or {},
            "temperature_c": (snap.get("system") or {}).get("temperature_c"),
            "profile": (snap.get("mission") or {}).get("current_profile"),
            "specialists": {
                "scratch_loaded": specialists["scratch_v5"].get("loaded"),
                "scratch_latency_ms": specialists["scratch_v5"].get("total_latency_ms"),
                "scratch_health": specialists["scratch_v5"].get("health"),
                "missing_loaded": specialists["missing_hole_v1"].get("loaded"),
                "missing_latency_ms": specialists["missing_hole_v1"].get("total_latency_ms"),
            },
        },
        "diagnose_ms": elapsed_ms,
    }
    return report


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
