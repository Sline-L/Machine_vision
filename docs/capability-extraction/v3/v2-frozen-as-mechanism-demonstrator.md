# LATENCY_DEGRADED_V2 — frozen engineering decision

```text
date: 2026-09-15
branch: srtp-agent/v2-pressure-pilot
decision: FREEZE V2 AS MECHANISM DEMONSTRATOR
          DO NOT SPEND FRESH HOLDOUT ON V2
```

## Official freeze

```text
LATENCY_DEGRADED_V2

Mechanism:                    PASS
Moderate latency recovery:    PRELIMINARY SUPPORTED   (S1)
Severe-pressure mitigation:   SUPPORTED               (S2/S3)
Severe-pressure recovery:     NOT SUPPORTED

Quality (consumed diagnostic): MATERIAL RISK  (ΔQ_D ≈ −0.193)
Mission admission:            NOT ESTABLISHED
Production:                   DISABLED
  implemented=true
  mission_approved=false
  available=false
```

V2 is **not** the final candidate for fresh-holdout admission spend.

## Why (latency succeeded; quality blocks admission path)

```text
S0: FULL ~186 → V2 ~136   both healthy
S1: FULL ~226 → V2 ~178   FULL FAIL / V2 PASS   ← envelope
S2: FULL ~321 → V2 ~257   both FAIL
S3: FULL ~400 → V2 ~323   both FAIL
```

A3 design thesis confirmed: fault needs a degradation that **truly reduces per-inspection workload**.  
SPARSE did not; V2 did (moderate recovery).

But diagnostic on consumed `test_scratch`:

```text
FULL Q_D = 0.806
V2   Q_D = 0.613
ΔQ_D     = −0.193

ResNet changed verdict 27×
  26× suppress false positive
   0× rescue false negative
```

Architecture read: **ResNet is primarily a normal / FP veto** in FULL. Removing it lets EffNet+detector over-call defects.

## Fresh holdout policy (updated)

```text
DO NOT run V2 (or any unfrozen candidate) on future fresh Scratch holdout.
Teammate may continue collecting / sealing.
Seal → no candidate runs → develop & freeze V3 primary → then one-shot holdout.
```

Fresh holdout is scarce. Diagnostic FPR risk is already strong enough to avoid consuming it on V2.

## Dual V3 recommendation (not conflicting)

```text
For proving moderate latency recovery:
  V3 NOT NECESSARY
  (V2 already demonstrated S1 FULL FAIL / V2 PASS)

For obtaining a mission-capable,
quality-preserving A3 profile:
  V3 RECOMMENDED / LIKELY NECESSARY
```

## Capability ladder (research)

```text
SPARSE  → workload not reduced → latency recovery fails
V2      → workload reduced → moderate recovery works → FP quality collapses
V3      → restore FP suppression at ≲10–12 ms extra S1 p95 vs V2
```

See [v3-lightweight-fp-veto-spec.md](v3-lightweight-fp-veto-spec.md).
