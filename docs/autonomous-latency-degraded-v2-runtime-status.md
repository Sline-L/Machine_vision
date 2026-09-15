# Autonomous LATENCY_DEGRADED_V2 runtime — status

```text
Agent core                         DONE
Capability registry                DONE
V2 runtime implementation          DONE
V2 topology switch                 PASS
V2 rollback                        PASS
V2 engineering soak                PASS

V2 healthy latency improvement     SUPPORTED
V2 pressured latency mitigation    SUPPORTED (S2/S3)
V2 moderate-pressure recovery      PRELIMINARY SUPPORTED (S1 envelope)
V2 severe-pressure recovery        NOT SUPPORTED (S2/S3)

V2 quality vs FULL (consumed test) MATERIAL RISK (diagnostic only; ΔQ_D≈−0.193)
V2 quality admission               BLOCKED ON FRESH HOLDOUT
A3 Mission recovery                PARTIAL (moderate only; not end-to-end A3)
A3 effectiveness                   NOT ESTABLISHED

REGISTRY
  implemented=true
  mission_approved=false
  available=false
```

## Two independent blockers (+ latency nuance)

| blocker | status |
| --- | --- |
| Capability admission | `FRESH SCRATCH-ONLY HOLDOUT` |
| A3 severe Mission-recovery | `V2 DOES NOT RESTORE GATE UNDER S2/S3` |
| Moderate recovery | S1 envelope **exists** (FULL FAIL / V2 PASS ×2) — not a holdout substitute |

## Severity sweep (preregistered)

See `docs/capability-extraction/v3/v2-severity-sweep-nx.{json,md,csv}`.

| S | replicas | FULL p95 (mean) | V2 p95 (mean) | envelope? |
| --- | ---: | ---: | ---: | --- |
| S0 | 0 | ~187 | ~136 | n/a |
| S1 | 1 | ~226 | ~178 | **YES** |
| S2 | 2 | ~321 | ~257 | no |
| S3 | 3 | ~400 | ~323 | no |

## Diagnostic quality (consumed `test_scratch`)

See `v2-test_scratch-diagnostic-comparison.md`.  
**Not admission.** ResNet mainly suppresses FPs (26); V2 Q_D 0.613 vs FULL 0.806.

## Decision matrix

| Dimension | Evidence | Status |
| --- | --- | --- |
| Healthy latency | integrated NX | supported |
| Severe pressure mitigation | S3 | supported |
| Moderate recovery | severity sweep S1 | **preliminary supported** |
| Runtime switch | NX engineering | pass |
| Rollback | pressure | pass |
| Soak | 30 min | pass |
| Relative quality vs FULL | consumed test_scratch | diagnostic only — material risk |
| Formal V2 quality | fresh holdout | blocked |
| A3 effectiveness | end-to-end | not established |

## V3 recommendation

```text
V3 NOT YET NECESSARY
```

(for moderate Mission-latency recovery). Do not auto-train. Revisit if severe gate recovery and/or quality parity are required.

## Git

| item | value |
| --- | --- |
| branch | `srtp-agent/v2-pressure-pilot` |
| teammate dataset tip audited | `dca0306` (unchanged) |
