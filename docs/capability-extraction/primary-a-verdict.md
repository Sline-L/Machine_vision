# Primary A status — blocked on vision capability

```text
Primary A — latency-targeted degradation
BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY

classifier_only_v1
REJECTED BY LOCKED MISSION CONTRACT

Not labeled "FAILED" as an Agent/runtime outcome:
  detection / switch / Verify / rollback requirements are defined.
  What is missing is a mission-grade lightweight vision capability.
```

## Detail (unchanged evidence)

```text
LATENCY FEASIBILITY       PASS   (~62–64 ms cls-only p95 vs ~261–276 ms FULL)
VAL CAPABILITY            PASS   (R=0.9535 FPR=0.0935 Q_D,val=0.9065)
LOCKED GENERALIZATION     FAIL   (R=0.8387 FPR=0.4454 Q_D,test=0.5546)
MISSION CONTRACT          FAIL   (U_test=0.7773 < 0.85)
RUNTIME ADMISSION         REJECTED
CLASSIFY_ONLY             NOT IMPLEMENTED
```

## Research finding

> Removing the detector substantially reduces per-inference latency, but the frozen classifier-only capability fails to generalize to the locked test set, primarily because of a large increase in false positives. Therefore, latency reduction alone is insufficient for admission as a mission-capable degradation profile.

The contract did its job: a fast but non-mission-grade profile was not admitted.

## Forbidden

```text
no threshold retune on test_scratch
no Candidate B locked rescue on the same test_scratch
no lowering Q_D / U floors to force CLASSIFY_ONLY
```

## Continue Primary A only via

```text
new vision lightweight capability (train/val)
→ freeze operating point
→ fresh independent holdout (not consumed test_scratch)
→ formal evaluation
→ PASS then reopen runtime gate
```

`test_scratch` may be used for **diagnostics** only.

Locked-test record: [locked-test/README.md](locked-test/README.md).
