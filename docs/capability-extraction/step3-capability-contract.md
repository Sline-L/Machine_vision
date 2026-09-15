# Step 3 — Capability + Mission contract

## Status at Step 3 close + Step 4 protocol

```text
STEP 3: CLOSED
STEP 4 PROTOCOL: FROZEN (see step4-locked-test-protocol.md)
test_scratch: NOT YET
CLASSIFY_ONLY: NOT STARTED
```

## Deliverables

| file | role |
| --- | --- |
| [classifier_only_v1.capability.json](classifier_only_v1.capability.json) | objective facts |
| [classifier_only_v1.mission-contract.md](classifier_only_v1.mission-contract.md) | \(Q_D\) + semantics + acceptance |
| [classifier_only_v1.contract.frozen.json](classifier_only_v1.contract.frozen.json) | single freeze record for handoff |
| this file | Step 3 close + gate |

## Semantics verdict (PASS)

Mission-critical binary Scratch verdict **PRESERVED**; auxiliary bbox **DEGRADED** and accepted as non-mission-critical under current GearPro (`is_defective` / serial / Mission Verify — no bbox gate).

Locked-test acceptance **excludes** bbox completeness by preregistration.

## \(Q_D\) (locked)

\[
Q_D = \min(\mathrm{Recall},\,1-\mathrm{FPR})
\]

\(Q_D,\mathrm{val}=0.9065\), \(U_\mathrm{val}\approx0.953\) — clears \(Q_D\ge0.70\) / \(U\ge0.85\).

## Coding gate at Step 3 close

```text
val freeze / latency / provenance     PASS
Q_D assignment rule                   PASS
Q_D,val = 0.9065 >= 0.70              PASS
Mission semantics acceptance          PASS
------------------------------------------------
Capability contract                   FROZEN
CLASSIFY_ONLY implementation          STILL NOT STARTED
```

## Next (strict order)

```text
frozen contract (this step)
        ↓
one locked test_scratch evaluation
  — same threshold
  — same Q_D formula (plug in locked R/FPR)
  — bbox loss NOT an acceptance criterion
  — NO retune of threshold or Q_D rule
        ↓
PASS / FAIL vs pre-registered criteria
        ↓
if PASS → open GearPro CLASSIFY_ONLY runtime
        ↓
latency-A3 under multi_bandwidth×3
```

### Pre-registered locked-test acceptance (binary capability only)

```text
threshold unchanged (0.5986470981744116)
Q_D_locked = min(Recall_locked, 1 - FPR_locked)
Q_D_locked >= 0.70
U_locked = 0.5 + 0.5*Q_D_locked >= 0.85   (assuming Q_L=Q_S=1 for quality report)
bbox / localization metrics: NOT CRITERIA
```

(Exact locked-test sample protocol lives with dataset `evaluate_scratch_v5_test.py --config`; run once.)

## Decision log

| date | decision |
| --- | --- |
| 2026-09-15 | Adopted \(Q_D=\min(R,1-\mathrm{FPR})\); semantics PENDING |
| 2026-09-15 | Semantics PASS from GearPro Mission code path; Step 3 CLOSED; locked test next; CLASSIFY_ONLY not started |
