# Step 4 result — one-shot locked `test_scratch`

```text
EXECUTED: once
rules_changed: false
threshold: 0.5986470981744116 (unchanged)
Q_D rule: min(Recall, 1-FPR) (unchanged)
```

Protocol: [step4-locked-test-protocol.md](../step4-locked-test-protocol.md)  
Report: [classifier_only_v1.locked-test.report.json](classifier_only_v1.locked-test.report.json)

## Metrics

| metric | value |
| --- | ---: |
| TP / FP / TN / FN | 26 / 53 / 66 / 5 |
| Recall | 0.8387 |
| FPR | 0.4454 |
| Specificity | 0.5546 |
| Precision | 0.3291 |
| F1 | 0.4727 |
| **Q_D,test** | **0.5546** |
| **U_test** | **0.7773** |

n = 150 (31 scratch / 119 normal)

## Dual judgments

```text
dataset_target_pass   = false   (R=0.8387 < 0.95; FPR=0.4454 > 0.20)
mission_contract_pass = false   (Q_D,test=0.5546 < 0.70)
runtime_gate          = CLOSED
```

## Branch taken (preregistered FAIL)

```text
→ CLASSIFY_ONLY runtime implementation NOT opened
→ do not tune A on test_scratch
→ do not select/tune B using this observed test_scratch as locked evidence
→ return to validation/design
→ next formal capability requires a fresh independent holdout
```

`test_scratch` has now been **seen** under this protocol; it is no longer blind for Candidate A (or for locked reuse by B).

## Research finding (design chapter)

> Removing the detector substantially reduces per-inference latency, but the frozen classifier-only capability fails to generalize to the locked test set, primarily because of a large increase in false positives. Therefore, latency reduction alone is insufficient for admission as a mission-capable degradation profile.

Project verdict: [primary-a-verdict.md](../primary-a-verdict.md)
