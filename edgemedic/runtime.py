"""P0 recovery tick: L0 → L1 → MEM → L2(4B) → Authority → Control → Verify.

Default execution_mode=observe_only never POSTs mutating actions.
execution_mode=execute_replay allows whitelist low-risk actions on an isolated Control.
"""

from __future__ import annotations

import time
import uuid

from .adapter import adapt_snapshot, specialist_view
from .authority import decide_execution
from .client import ControlClient
from .incident import build_incident
from .memory import EpisodeStore
from .policy import Memory, classify_fault, decide
from .readonly_client import ReadOnlyControlClient
from .reasoner import DECODE_GRAMMAR, INPUT_STRUCTURED, ReasonerError, complete_report

L2_COOLDOWN_S = 30.0
MEM_COOLDOWN_S = 10.0
EXECUTE_OBSERVE = "observe_only"
EXECUTE_REPLAY = "execute_replay"


def _verify_level(result):
    if not result:
        return "none"
    if result.get("verify_level"):
        return result["verify_level"]
    if result.get("verified"):
        return "function"
    return "none"


def _config_ok(result):
    if result is None:
        return False
    return _verify_level(result) in ("function", "mission", "config")


def recovery_outcome(result=None, l2_error=None):
    if l2_error:
        text = str(l2_error).lower()
        if "timeout" in text or "timed out" in text:
            return "TIMEOUT"
        return "FAILED"
    if not result:
        return None
    error = str(result.get("error") or "").lower()
    if "timeout" in error or "timed out" in error:
        return "TIMEOUT"
    if result.get("recovery_success") or _verify_level(result) in ("function", "mission"):
        return "RECOVERED"
    if result.get("accepted") is False:
        return "FAILED"
    if result.get("executed") and not result.get("recovery_success"):
        return "FAILED"
    if result.get("dry_run"):
        return "DRY_RUN"
    return "FAILED"


def _preview(client, action, source):
    return client.preview_action(
        action["name"],
        params=action.get("params") or {},
        source=source,
        request_id=action.get("request_id") or f"{source}-preview",
    )


def _execute(client, action, source):
    started = time.monotonic()
    result = client.post_action(
        action["name"],
        params=action.get("params") or {},
        source=source,
        request_id=action.get("request_id") or f"{source}-{uuid.uuid4().hex[:8]}",
    )
    result = dict(result or {})
    result.setdefault("control_latency_ms", round((time.monotonic() - started) * 1000.0, 1))
    return result


class LoopState:
    def __init__(self, store=None):
        self.memory = Memory()
        self.store = store if store is not None else EpisodeStore()
        self.last_l2 = 0.0
        self.last_mem = 0.0
        self.recent_actions = []


def make_client(control_url, execution_mode=EXECUTE_OBSERVE):
    if execution_mode == EXECUTE_REPLAY:
        return ControlClient(control_url, timeout=30.0)
    return ReadOnlyControlClient(base_url=control_url)


def run_once(
    client,
    state=None,
    *,
    llm_url=None,
    execution_mode=EXECUTE_OBSERVE,
    disable_l1=False,
    disable_memory=False,
    force_l2=False,
    l2_timeout=60.0,
    snapshot_overlay=None,
):
    """One Agent tick. Never bypasses Authority for L2."""
    if execution_mode not in (EXECUTE_OBSERVE, EXECUTE_REPLAY):
        raise ValueError(f"unsupported execution_mode: {execution_mode}")
    state = state or LoopState()
    t0 = time.monotonic()

    if snapshot_overlay is not None:
        raw = snapshot_overlay
    else:
        raw = client.get_state()
    snap = adapt_snapshot(raw)
    specialists = specialist_view(snap)

    fault = classify_fault(snap, state.memory)
    l1 = None if disable_l1 else decide(snap, state.memory)

    executed = None
    result = None
    layer = None
    incident = None
    proposed_action = None
    l2_report = None
    l2_error = None
    l2_latency_ms = None
    authority_gate = {
        "action_risk_class": None,
        "execution_authority": None,
        "would_execute": False,
        "note": None,
    }
    actually_executed = False
    route_selected = None
    why_l2 = None

    allow_mutate = execution_mode == EXECUTE_REPLAY and not isinstance(client, ReadOnlyControlClient)

    def _dispatch(action, source, *, via_authority=False):
        nonlocal result, actually_executed, authority_gate
        if via_authority:
            authority_gate = decide_execution(action, source="reasoner", live_research=True)
            if not authority_gate.get("would_execute"):
                if allow_mutate and hasattr(client, "preview_action"):
                    result = _preview(client, action, source)
                else:
                    result = {
                        "accepted": False,
                        "executed": False,
                        "dry_run": True,
                        "verify_level": "none",
                        "error": "authority_blocked",
                        "authority": dict(authority_gate),
                    }
                actually_executed = False
                return
        if not allow_mutate:
            # Keep Authority decision visible even when POST is structurally disabled.
            if via_authority:
                authority_gate = {
                    **authority_gate,
                    "would_execute_if_armed": bool(authority_gate.get("would_execute")),
                    "would_execute": False,
                    "note": "observe_only: Authority approved but Control POST skipped",
                }
            else:
                authority_gate = {
                    "action_risk_class": "OBSERVE",
                    "execution_authority": EXECUTE_OBSERVE,
                    "would_execute": False,
                    "note": "observe_only mode: proposal recorded, Control POST skipped",
                }
            result = {
                "accepted": False,
                "executed": False,
                "dry_run": True,
                "verify_level": "none",
                "error": None,
                "note": "observe_only",
                "authority": dict(authority_gate),
            }
            actually_executed = False
            return
        result = _execute(client, action, source)
        actually_executed = bool(result.get("executed"))
        if via_authority:
            result["authority"] = dict(authority_gate)

    # L0/L1
    if l1 is not None:
        layer = l1.get("layer") or "L1"
        route_selected = layer
        proposed_action = {"name": l1["name"], "params": l1.get("params") or {}, "layer": layer, "source": "reflex"}
        incident = build_incident(fault or l1.get("rule"), snap, l1, layer)
        _dispatch(l1, "reflex")
        executed = l1

    # MEM
    mem_ready = (time.monotonic() - state.last_mem) >= MEM_COOLDOWN_S
    if executed is None and fault and not disable_memory and mem_ready:
        suggested = state.store.suggest(fault)
        if suggested is not None:
            suggested = {
                **suggested,
                "request_id": f"MEM-{fault}-{uuid.uuid4().hex[:8]}",
                "layer": "MEM",
                "rule": fault,
                "source": "memory",
            }
            layer = "MEM"
            route_selected = "MEM"
            proposed_action = {"name": suggested["name"], "params": suggested.get("params") or {}, "layer": "MEM", "source": "memory"}
            incident = build_incident(fault, snap, suggested, "MEM", confidence=0.8)
            _dispatch(suggested, "memory")
            if allow_mutate:
                state.store.mark_suggestion(accepted=bool((result or {}).get("accepted")), verify_level=_verify_level(result))
            executed = suggested
            state.last_mem = time.monotonic()

    # L2 — only if no L1/MEM proposal, or force_l2 after L1 miss
    stuck = executed is not None and allow_mutate and not _config_ok(result)
    need_l2 = bool(llm_url) and bool(fault) and (executed is None or stuck or force_l2)
    l2_ready = force_l2 or (time.monotonic() - state.last_l2) >= L2_COOLDOWN_S
    if need_l2 and l2_ready and (executed is None or stuck or (force_l2 and executed is None)):
        why_l2 = []
        if disable_l1:
            why_l2.append("disable_l1")
        if executed is None:
            why_l2.append("no_l1_or_mem_proposal")
        if stuck:
            why_l2.append("prior_action_verify_failed")
        if force_l2:
            why_l2.append("force_l2")
        note = ""
        if stuck:
            note = f"Previous action {(executed or {}).get('name')} failed verify: {(result or {}).get('error')}"
        t_l2 = time.monotonic()
        try:
            l2_report = complete_report(
                llm_url,
                snap,
                extra_note=note or "Prefer restart_camera for stale camera; resume_inspection for paused mission; abstain if unsure.",
                timeout=l2_timeout,
                fault=fault,
                experience=[],
                recent_actions=state.recent_actions,
                input_mode=INPUT_STRUCTURED,
                decode=DECODE_GRAMMAR,
            )
            proposed = l2_report.get("action")
        except ReasonerError as exc:
            l2_error = str(exc)
            l2_report = {"error": l2_error, "invalid": True}
            proposed = None
        l2_latency_ms = round((time.monotonic() - t_l2) * 1000.0, 1)
        if l2_report is not None and l2_report.get("latency_s") is not None:
            l2_latency_ms = round(float(l2_report["latency_s"]) * 1000.0, 1)
        state.last_l2 = time.monotonic()
        layer = "L2"
        route_selected = "L2"
        if proposed is not None:
            proposed["request_id"] = f"L2-{uuid.uuid4().hex[:8]}"
            proposed_action = {
                "name": proposed.get("name"),
                "params": proposed.get("params") or {},
                "layer": "L2",
                "source": "reasoner",
            }
            incident = build_incident(fault or "UNKNOWN", snap, proposed, "L2", confidence=0.5)
            _dispatch(proposed, "reasoner", via_authority=True)
            executed = proposed
        else:
            proposed_action = None
            authority_gate = {
                "action_risk_class": "OBSERVE",
                "execution_authority": "OBSERVE",
                "would_execute": False,
                "note": "L2 abstain/invalid",
            }

    if incident is None and fault:
        incident = build_incident(fault, snap, executed or {}, layer)

    snapshot_after = None
    if actually_executed:
        try:
            snapshot_after = adapt_snapshot(client.get_state())
        except Exception:
            snapshot_after = None
        if fault and executed is not None:
            state.store.record(
                fault,
                executed["name"],
                executed.get("params") or {},
                verify_level=_verify_level(result),
            )

    if executed is not None:
        state.recent_actions.append(
            {
                "name": executed.get("name"),
                "layer": layer,
                "accepted": None if result is None else result.get("accepted"),
                "verify_level": _verify_level(result),
            }
        )
        state.recent_actions = state.recent_actions[-5:]

    outcome = recovery_outcome(result, l2_error=l2_error)
    return {
        "fault": fault,
        "diagnosis": None if incident is None else incident.get("diagnosis"),
        "route": {
            "selected": route_selected,
            "l1_hit": l1 is not None,
            "memory_hit": route_selected == "MEM",
            "l2_invoked": l2_report is not None,
            "why_l2": why_l2,
            "disable_l1": disable_l1,
        },
        "proposed_action": proposed_action,
        "authority_decision": authority_gate,
        "execution_mode": execution_mode,
        "actually_executed": actually_executed,
        "control_result": result,
        "verify_level": _verify_level(result),
        "recovery_outcome": outcome,
        "l2": None
        if l2_report is None
        else {
            "invoked": True,
            "error": l2_error or l2_report.get("error"),
            "invalid": l2_report.get("invalid"),
            "protocol_status": l2_report.get("protocol_status") or l2_report.get("invalid_class"),
            "latency_s": l2_report.get("latency_s"),
            "latency_ms": l2_latency_ms,
            "prompt_tokens": l2_report.get("prompt_tokens"),
            "completion_tokens": l2_report.get("completion_tokens"),
            "tokens": l2_report.get("tokens"),
            "decode": l2_report.get("decode"),
            "model": "qwen3-4b",
            "raw_preview": (l2_report.get("raw") or "")[:300],
            "action": None
            if proposed_action is None or proposed_action.get("layer") != "L2"
            else proposed_action,
        },
        "specialists": specialists,
        "evidence": None if incident is None else incident.get("evidence"),
        "metrics": {
            "e2e_latency_ms": round((time.monotonic() - t0) * 1000.0, 1),
            "l2_latency_ms": l2_latency_ms,
            "control_latency_ms": None if result is None else result.get("control_latency_ms", result.get("duration_ms")),
        },
        "snapshot_schema": snap.get("schema_version"),
        "ACTUAL_EXECUTION_DISABLED": execution_mode == EXECUTE_OBSERVE,
    }
