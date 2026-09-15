# Autonomous LATENCY_DEGRADED_V2 runtime — status

```text
LATENCY_DEGRADED_V2
ENGINEERING IMPLEMENTATION COMPLETE

HEALTHY INTEGRATED LATENCY          PASS
PRESSURE LATENCY RECOVERY           MITIGATION SUPPORTED (gate recovery NOT ESTABLISHED)
ENGINEERING SOAK                    PASS

FORMAL QUALITY ADMISSION
  BLOCKED ON FRESH SCRATCH-ONLY HOLDOUT

REGISTRY
  implemented=true
  mission_approved=false
  available=false

A3 EFFECTIVENESS                    NOT ESTABLISHED
```

## Git

| item | value |
| --- | --- |
| evidence branch | `srtp-agent/v2-pressure-pilot` |
| runtime base | `integration/latency-degraded-v2-runtime` @ `b3f5cc5` |
| worktree | `G:/CODE/Machine_vision-ldv2-runtime` |
| backup (pre pressure) | `backup/pre-v2-pressure-soak-20260915-152758` |
| push | `origin/srtp-agent/v2-pressure-pilot` |

## Frozen candidate

| field | value |
| --- | --- |
| profile | `LATENCY_DEGRADED_V2` (`latency_degraded_v2_effnet_det`) |
| classifier | EffNet-B0@384 `classifier_1.pt` SHA `44461f4e…` |
| detector | P2@960 `detector.pt` SHA `4451e3f3…` |
| fusion | weighted α=0.25, `classifier_single` |
| threshold | `0.2653394325872992` |
| NX experimental p95 | 85.9 ms (early isolated probe only) |
| NX integrated p95 | **wall 129.5 ms** vs FULL **189.1 ms** (planning baseline) |
| formal_holdout_status | MISSING |

## Registry

```text
implemented = true
mission_approved = false
available = false
```

## NX Pressure Pilot

Evidence: `docs/capability-extraction/v3/v2-pressure-pilot-nx.{json,md}`

| item | value |
| --- | --- |
| lean A–F | PASS |
| FULL pressure wall p95 | **397.6 ms** (gate FAIL, sustained overload) |
| V2 pressure wall p95 | **318.4 ms** (gate FAIL, cls2=0) |
| ratio V2/FULL | **0.80** |
| injector alive through switch/rollback | yes |
| LATENCY MITIGATION | SUPPORTED |
| MISSION LATENCY RECOVERY | NOT ESTABLISHED |
| ENGINEERING SOAK 30 min | PASS (global p95 136.6 ms, RSS +117 MiB, 0 exceptions) |

Previous silent run (~36 min, buffered log): recorded as
`SUSPICIOUS_ENGINEERING_EVENT` with **buffering vs hang UNDETERMINED** — no research
conclusion. See `v2-pressure-previous-run-event.md`.

## Formal blocker

```text
ONLY FORMAL BLOCKER:
FRESH SCRATCH-ONLY HOLDOUT
```
