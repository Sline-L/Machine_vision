# Capability admission state machine

Fail-closed. No profile becomes Agent-switchable without both:

```text
implemented == true
AND
mission_approved == true
```

## States

```text
DISCOVERED
  → VAL_FROZEN
  → LATENCY_CHARACTERIZED
  → MISSION_CONTRACT_FROZEN
  → FORMAL_HOLDOUT_PASS
  → RUNTIME_IMPLEMENTED
  → NX_VERIFIED
  → A3_ELIGIBLE

FORMAL_HOLDOUT_FAIL → REJECTED   (terminal for that capability id)
```

## Current registry highlights

| profile_id | status |
| --- | --- |
| FULL | A3_ELIGIBLE (baseline) |
| SPARSE | A3_ELIGIBLE (cadence only; not latency/capacity recovery) |
| SAFE_STOP / TRT_FAST | available per existing profile rules |
| classifier_only_v1 | **REJECTED** (formal holdout fail) |
| CLASSIFY_ONLY | DISCOVERED / unimplemented / not approved |
| LOCATE_ONLY | DISCOVERED / unimplemented / not approved |

Rejected capabilities must never flip to `available` merely because a registry
row exists.
