# V3-1 fresh holdout — preregistered acceptance criteria

```text
status: PREREGISTERED — NOT EXECUTED
fresh_holdout: SEALED / UNTOUCHED
candidate: scratch_v3_1_fp_veto_logistic (engineering freeze)
written_before_holdout_open: true
```

## Purpose

One-shot confirmatory adjudication of frozen V3-1 on a **future** sealed fresh Scratch holdout.  
This document is committed **before** any holdout images are scored by V3-1.

## Forbidden until adjudication package is opened

- Changing V3-1 threshold, features, weights, or fusion mode
- Training / selecting on holdout
- Multiple peek-and-retry runs
- Spending the holdout on V2 or unfrozen candidates first

## Metrics to report (mandatory)

Always report **all** of:

```text
Q_D = min(Recall, Specificity)
FPR
Recall
Specificity
Precision
F1
TP FP TN FN
```

Do **not** adjudicate on Q_D alone.

## Baseline comparisons (same holdout, same protocol)

| arm | definition |
| --- | --- |
| FULL | Scratch V5 two-classifier + detector (reference) |
| V2 | frozen LATENCY_DEGRADED_V2 |
| V3-1 | frozen V2 backbone + logistic `replace_score` @ freeze threshold |

## Acceptance patterns (locked)

### PASS — V3-1 succeeds as quality-preserving mechanism

All of:

1. `Q_D(V3-1) ≥ 0.70` (EdgeMedic Mission floor, QL=QS=1)
2. `Q_D(V3-1) > Q_D(V2)` by a clear margin (**≥ +0.02** absolute)
3. `FPR(V3-1) < FPR(V2)` by a clear margin (**≤ −0.03** absolute, i.e. at least 3 pp drop)
4. Recall drop vs V2 is **limited**: `Recall(V2) − Recall(V3-1) ≤ 0.08`
5. No evidence of collapse vs FULL beyond documented domain gap narrative

Interpretation: FPR suppression holds out-of-domain; recall cost remains acceptable.

### FAIL-A — Aggressive veto (Q_D may still look OK)

Any of:

- `Recall(V2) − Recall(V3-1) > 0.08`, **or**
- FN surge concentrated on easy/high-confidence scratches (manual review flag)

Even if `Q_D ≥ 0.70`.

### FAIL-B — Val artifact / no transferable FP suppression

- `FPR(V2) − FPR(V3-1) < 0.02` (little/no FPR gain), **or**
- `Q_D(V3-1) ≤ Q_D(V2)`

Interpretation: logistic veto did not transfer; revisit V3-2 distillation (still without burning another holdout until re-freeze).

### FAIL-C — Mission floor miss

- `Q_D(V3-1) < 0.70`

## Explicit non-claims after PASS

PASS does **not** automatically mean:

```text
mission_approved=true
production available
A3 effectiveness established
```

Those require separate registry + runtime + A3 protocol steps.

## Latency gate (already decided separately)

Holdout adjudication assumes NX S1 paired latency already **PASS**:

```text
V3-1 integrated p95 < 190 ms
delta_p95 = V3-1 − V2  within ~10–12 ms budget
```

If S1 latency FAIL, do **not** open holdout for V3-1.

## One-shot protocol

```text
1. Seal holdout (manifest + hash) without model scores
2. Confirm V3-1 engineering freeze hash unchanged
3. Confirm S1 paired latency PASS on record
4. Run FULL / V2 / V3-1 once each
5. Write locked report
6. Apply PASS / FAIL-A / FAIL-B / FAIL-C above
7. Stop
```

---

## PRE-HOLDOUT PREREGISTRATION AMENDMENT

```text
status: AMENDMENT — BEFORE ANY HOLDOUT EXECUTION OR INSPECTION
fresh_holdout_status_at_amendment: UNTOUCHED
candidate_commit: e8b2b0fda2af2c9c8c697d4655d527947381377a
numeric_gates: UNCHANGED
```

This amendment does **not** change the locked numeric thresholds in the original PASS / FAIL-A / FAIL-B / FAIL-C clauses. It only closes pre-execution logic gaps. Commit history for this change must keep:

```text
PRE-HOLDOUT AMENDMENT
fresh holdout status at amendment: UNTOUCHED
numeric thresholds unchanged
```

### Overall verdict (mechanical)

FAIL-A / FAIL-B / FAIL-C are **non-exclusive failure flags**.

```text
if one or more FAIL flags trigger:
    overall = FAIL
else if ALL mechanical PASS conditions trigger:
    overall = PASS
else:
    overall = INCONCLUSIVE
```

Mechanical PASS conditions are original items 1–4 only:

```text
1. Q_D(V3-1) >= 0.70
2. Q_D(V3-1) - Q_D(V2) >= 0.02
3. FPR(V2) - FPR(V3-1) >= 0.03
4. Recall(V2) - Recall(V3-1) <= 0.08
```

Therefore FPR reduction in `[0.02, 0.03)` is **INCONCLUSIVE** (not PASS, not FAIL-B). Do not widen FAIL-B to 0.03 and do not relax PASS to 0.02.

No extra categories (`soft pass`, `near pass`, `engineering pass`).

### Subjective clauses — locked status before holdout

Original PASS item 5 (`collapse vs FULL`) and FAIL-A item 2 (`FN surge on easy/high-confidence scratches`) are **not mechanical gates**.

They are secondary manual-review flags. They **must not** change `overall`.

#### easy/high-confidence scratch (frozen operational definition)

```text
ground_truth == 1
AND full_prediction == 1
AND v2_prediction == 1
```

Meaning: both frozen operating points already predict scratch. Count `v3_1_prediction == 0` on that subset as `fn_on_easy_high_confidence_*`. Report only. `triggers_FAIL_A = false`.

Mechanical FAIL-A is solely:

```text
Recall(V2) - Recall(V3-1) > 0.08
```

#### collapse vs FULL (frozen operational definition)

```text
record Q_D(FULL) - Q_D(V3-1)
do not mechanically fail or pass on this gap
human narrative review only after CONSUMED lock
cannot rewrite overall
```

### After any formal scoring of the sealed population

```text
fresh_holdout = CONSUMED
```

regardless of PASS / FAIL / INCONCLUSIVE / runtime error after exposure. Registry remains unmodified.
