# Step 4 — Locked-test protocol (FROZEN before any `test_scratch` run)

```text
STEP 4 PROTOCOL STATUS: FROZEN
test_scratch executed under this protocol: YES (one shot)
mission_contract_pass: false
runtime_gate: CLOSED
CLASSIFY_ONLY implementation: NOT STARTED
```

Result: [locked-test/README.md](locked-test/README.md)

Parent contract: [classifier_only_v1.contract.frozen.json](classifier_only_v1.contract.frozen.json).

---

## LOCKED TEST PROTOCOL — `classifier_only_v1`

### Frozen inputs

```text
fusion        = classifier_mean
models        = classifier_1 + classifier_2
detector      = disabled
threshold     = 0.5986470981744116
Q_D rule      = min(Recall, 1 - FPR)
bbox          = not an acceptance criterion
config        = docs/capability-extraction/configs/classifier_only_mean.val-frozen.json
               (or equivalent export with identical threshold / fusion / temps / SHAs)
```

### Forbidden (entire Step 4 + after FAIL)

```text
- threshold tuning
- model / fusion switching for a “better” test score
- recalibration / temperature refit on test
- test-driven Q_D rule changes
- deleting unfavorable samples or discarding runs
- using observed test_scratch results to select or tune Candidate B
  while still calling the same set a “locked test”
```

### Run discipline

```text
exactly one formal evaluation on locked test_scratch
report all metrics below
no second “official” pass after looking at scores
```

Evaluator: dataset `evaluate_scratch_v5_test.py --config <frozen classifier_only config>`  
(or GearPro-equivalent that uses the same scores / threshold; must not touch detector).

### Reported metrics

```text
TP / FP / TN / FN
Recall
FPR
Specificity = 1 - FPR
Precision / F1
Q_D,test = min(Recall, Specificity)
U_test   = 0.5 + 0.5 * Q_D,test     # Q_L = Q_S = 1 quality report
```

Also record: config hash, weight SHAs, dataset commit / test set id, run timestamp, command line.

---

## Two independent judgments (do not conflate)

Dataset-side selection target (FULL train pipeline) and Mission contract are **different**.

```text
dataset_target_pass
  = (Recall >= 0.95) AND (FPR <= 0.20)

mission_contract_pass
  = (Q_D,test >= 0.70)
    AND binary Mission semantics preserved
        (same as Step 3: binary Scratch verdict; bbox not required)
```

| judgment | role |
| --- | --- |
| `dataset_target_pass` | Generalization vs original train/val **selection target** — report only |
| `mission_contract_pass` | **Sole** gate for runtime `CLASSIFY_ONLY` |

```text
runtime_gate =
  OPEN only if mission_contract_pass == true
```

It is valid to have:

```text
mission_contract_pass = true
dataset_target_pass   = false
```

That is still a Mission-contract PASS for opening runtime (report the dataset miss clearly).  
Conversely, dataset target pass without \(Q_D,\mathrm{test}\ge0.70\) does **not** open runtime.

---

## Formal result (executed)

```text
dataset_target_pass   = false
mission_contract_pass = false
runtime_gate          = CLOSED
RUNTIME ADMISSION     = REJECTED
CLASSIFY_ONLY         = NOT IMPLEMENTED
```

See [locked-test/README.md](locked-test/README.md) and [primary-a-verdict.md](primary-a-verdict.md).

---

## Failure branch (preregistered)

### If `mission_contract_pass == true`

```text
→ runtime implementation gate OPEN
→ may implement GearPro CLASSIFY_ONLY (implemented=true)
→ then latency-A3 under multi_bandwidth×3
```

### If `mission_contract_pass == false`

```text
→ runtime_gate remains CLOSED
→ do not tune A on test_scratch
→ do not select / tune Candidate B using observed test_scratch results
→ return to validation / design stage
→ any next formal capability requires a fresh independent holdout
  (or explicitly downgrade reuse of this test_scratch to exploratory-only,
   never again as locked formal evidence)
```

**After this one look at `test_scratch`, the set is no longer blind.**  
Candidate B may remain documented as a fallback design, but must not be “rescued” on the same locked labels.

---

## Execution order

```text
Step 3 contract freeze                 DONE
Step 4 locked-test protocol freeze     DONE (this document)
        ↓
run test_scratch exactly once
        ↓
compute Q_D,test / U_test
        ↓
dataset_target_pass + mission_contract_pass
        ↓
runtime_gate = OPEN iff mission_contract_pass
```

---

## Coding / runtime gate (pre-run)

```text
val freeze / latency / provenance     PASS
Q_D assignment rule                   PASS
Q_D,val >= 0.70                       PASS
Mission semantics acceptance          PASS
Capability contract                   FROZEN
Locked-test protocol                  FROZEN
test_scratch run                      NOT YET
CLASSIFY_ONLY implementation          NOT STARTED
```

## Decision log

| date | decision |
| --- | --- |
| 2026-09-15 | Step 4 protocol frozen before any test_scratch access; dual pass criteria + FAIL branch preregistered |
