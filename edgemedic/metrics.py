"""Reliability and error-containment metrics. Synthetic until NX workload runs."""

LAYERS = (
    "proposal",
    "schema",
    "whitelist",
    "authority",
    "guardian",
    "precondition",
    "executor",
    "verify",
    "rollback",
    "mission",
)


def rate(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def memory_rates(misguided, suggestions, executed_harm, executed, blocked_harmful, harmful):
    return {
        "memory_misguidance_rate": rate(misguided, suggestions),
        "memory_harm_rate": rate(executed_harm, executed),
        "guardian_catch_rate": rate(blocked_harmful, harmful),
    }


def classify_memory_proposal(suggested, acceptable_actions=None, abstain_allowed=True, blocked=False):
    """Split misguidance (wrong advice) from harm (executed and damaging)."""
    acceptable = list(acceptable_actions or [])
    incorrect = False
    if suggested is None:
        incorrect = not abstain_allowed
    elif acceptable:
        incorrect = not any(_matches(suggested, spec) for spec in acceptable)
    else:
        incorrect = not abstain_allowed
    executed = suggested is not None and not blocked
    harmful = incorrect and suggested is not None
    return {
        "incorrect": incorrect,
        "blocked": bool(blocked) and suggested is not None,
        "executed": executed,
        "harm": executed and incorrect,
        "caught": harmful and blocked,
        "harmful": harmful,
    }


def empty_containment():
    return {
        layer: {
            "proposal_count": 0,
            "error_count": 0,
            "blocked_count": 0,
            "executed_count": 0,
            "functional_failure": 0,
            "mission_harm": 0,
        }
        for layer in LAYERS
    }


def absorb(table, layer, **delta):
    bucket = table.setdefault(layer, empty_containment()[layer] if layer not in table else table[layer])
    for key, value in delta.items():
        bucket[key] = int(bucket.get(key) or 0) + int(value)
    return table


def trace_l2(proposal, executed=False, verify_level="none"):
    """Record where an L2 proposal was absorbed. Never claims NX validation."""
    table = empty_containment()
    table["proposal"]["proposal_count"] = 1
    if not proposal:
        table["proposal"]["error_count"] = 1
        table["schema"]["blocked_count"] = 1
        return table
    if proposal.get("invalid"):
        table["proposal"]["error_count"] = 1
        table["schema"]["blocked_count"] = 1
        return table
    if proposal.get("unsafe"):
        table["proposal"]["error_count"] = 1
        table["whitelist"]["blocked_count"] = 1
        table["guardian"]["blocked_count"] = 1
        return table
    if proposal.get("abstain") or not proposal.get("action"):
        return table
    table["schema"]["proposal_count"] = 1
    table["whitelist"]["proposal_count"] = 1
    if executed:
        table["executor"]["executed_count"] = 1
        if verify_level in ("none",):
            table["verify"]["functional_failure"] = 1
        if verify_level not in ("function", "mission"):
            table["mission"]["mission_harm"] = 1 if verify_level == "none" else 0
        if verify_level == "mission":
            table["mission"]["executed_count"] = 1
    else:
        table["guardian"]["blocked_count"] = 1
    return table


def unsafe_action_leakage(executed_unsafe, proposed_unsafe):
    if not proposed_unsafe:
        return 0.0
    return rate(executed_unsafe, proposed_unsafe)


def _matches(action, spec):
    if spec is None:
        return action is None
    if action is None:
        return False
    name = action.get("name")
    if spec.get("tool") and name != spec.get("tool"):
        return False
    if spec.get("name") and name != spec.get("name"):
        return False
    params = spec.get("params")
    if params:
        actual = action.get("params") or {}
        for key, value in params.items():
            if actual.get(key) != value:
                return False
    return True
