"""Deterministic L2 execution authority. LLM recommendation is not authority."""

from __future__ import annotations

OBSERVE = "OBSERVE"
DRY_RUN = "DRY_RUN"
AUTO_LOW_RISK = "AUTO_LOW_RISK"
REQUIRE_APPROVAL = "REQUIRE_APPROVAL"

# Profile / backend / mission-config switches stay propose-only for L2.
REQUIRE_APPROVAL_TOOLS = frozenset(
    (
        "set_inference_profile",
        "set_locator_profile",
        "reload_config",
        "rollback_config",
        "apply_settings",
        "use_camera",
        "use_video",
        "restart_worker",
    )
)

AUTO_LOW_RISK_TOOLS = frozenset(
    (
        "pause_inspection",
        "resume_inspection",
        "reconnect_serial",
        "restart_camera",
    )
)


def risk_class(action):
    if not action or not action.get("name"):
        return OBSERVE
    name = action.get("name")
    if name in REQUIRE_APPROVAL_TOOLS:
        return REQUIRE_APPROVAL
    if name in AUTO_LOW_RISK_TOOLS:
        return AUTO_LOW_RISK
    return REQUIRE_APPROVAL


def decide_execution(action, *, source="reasoner", live_research=True):
    """L2 live research defaults to dry-run unless AUTO_LOW_RISK.

    L1/memory are not gated here; they already use deterministic rules.
    """
    cls = risk_class(action)
    if not action or not action.get("name"):
        return {
            "action_risk_class": OBSERVE,
            "execution_authority": OBSERVE,
            "would_execute": False,
        }
    if source == "reasoner" and live_research and cls != AUTO_LOW_RISK:
        return {
            "action_risk_class": cls,
            "execution_authority": DRY_RUN,
            "would_execute": False,
        }
    if cls == AUTO_LOW_RISK:
        return {
            "action_risk_class": cls,
            "execution_authority": AUTO_LOW_RISK,
            "would_execute": True,
        }
    return {
        "action_risk_class": cls,
        "execution_authority": REQUIRE_APPROVAL,
        "would_execute": False,
    }
