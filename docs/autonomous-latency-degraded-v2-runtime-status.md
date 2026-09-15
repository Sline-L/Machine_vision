# Autonomous LATENCY_DEGRADED_V2 runtime — status

```text
LATENCY_DEGRADED_V2
FROZEN AS: moderate-latency recovery MECHANISM DEMONSTRATOR
NOT: final Mission-admissible capability

Mechanism:                         PASS
Moderate latency recovery:         PRELIMINARY SUPPORTED (S1)
Severe-pressure mitigation:        SUPPORTED (S2/S3)
Severe-pressure recovery:          NOT SUPPORTED

Quality (consumed diagnostic):     MATERIAL RISK (ΔQ_D ≈ −0.193)
Mission admission:                 NOT ESTABLISHED
Production:                        DISABLED
  implemented=true
  mission_approved=false
  available=false

Fresh holdout policy:              DO NOT RUN V2 — seal for V3 primary
A3 effectiveness:                  NOT ESTABLISHED
```

## Engineering decision (2026-09-15)

V2 **should not** consume a future fresh Scratch holdout.  
Spend that sealed set on a frozen **V3** primary after train/val selection.

Full freeze memo: [v2-frozen-as-mechanism-demonstrator.md](capability-extraction/v3/v2-frozen-as-mechanism-demonstrator.md)

## Latency evidence (unchanged facts)

```text
S0: FULL ~186 → V2 ~136
S1: FULL ~226 → V2 ~178   FULL FAIL / V2 PASS
S2: FULL ~321 → V2 ~257
S3: FULL ~400 → V2 ~323
```

A3 thesis confirmed: degradation must cut real per-inspection workload (SPARSE failed; V2 succeeded at moderate).

## Quality evidence (diagnostic only)

```text
FULL Q_D 0.806 → V2 Q_D 0.613
ResNet: 26× FP suppress, 0× FN rescue
→ ResNet ≈ normal / false-positive veto
```

## Dual V3 recommendation

```text
For proving moderate latency recovery:
  V3 NOT NECESSARY

For mission-capable, quality-preserving A3:
  V3 RECOMMENDED / LIKELY NECESSARY
```

## V3 latency budget (from S1)

```text
S1 V2 p95 ≈ 178 ms
Mission gate  = 190 ms
extra budget  ≈ 10–12 ms under S1

MUST NOT restore ~50 ms second backbone (FULL−V2 ≈ 48 ms)
```

Spec: [v3-lightweight-fp-veto-spec.md](capability-extraction/v3/v3-lightweight-fp-veto-spec.md)

Priority: (1) cheap feature veto (2) distill FP-veto into EffNet (3) ultra-light second model last.

## Decision matrix

| Dimension | Evidence | Status |
| --- | --- | --- |
| Healthy latency | integrated NX | supported |
| Severe mitigation | S3 | supported |
| Moderate recovery | S1 sweep | preliminary supported |
| Runtime switch / rollback / soak | NX | pass |
| Relative quality vs FULL | consumed test_scratch | material risk (diagnostic) |
| Formal V2 quality | fresh holdout | **do not spend on V2** |
| A3 effectiveness | end-to-end | not established |
| Next capability | V3 FP-veto / distill | **recommended for Mission A3** |

## Git

| item | value |
| --- | --- |
| branch | `srtp-agent/v2-pressure-pilot` |
| teammate dataset tip | `dca0306` |
