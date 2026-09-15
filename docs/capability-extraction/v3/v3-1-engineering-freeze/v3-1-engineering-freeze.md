# V3-1 Engineering Freeze

```text
status: V3-1 CANDIDATE PROMISING — ENGINEERING FREEZE
exploration_commit: 2377521f827ba8137025c6bb53afe590db1bd982
fresh_holdout: UNTOUCHED
registry: UNCHANGED
param_lock: NO CHANGES until after fresh-holdout adjudication
```

## Identity

| item | value |
| --- | --- |
| candidate_id | `scratch_v3_1_fp_veto_logistic` |
| freeze_package_hash | `b3724ee1e19dde5bc8343964b29ceaf58ebafec914b43d0346cd498362813683` |
| V2 config_hash | `5cc1730c0c9cdd83e8909e963184c759f4d29bec5ed4eab1bfe44f0ae13b4588` |
| classifier_1 SHA | `44461f4e03ff716266a3123bf1ba4611a1c965cf8776d0e523f128cf7c0b8438` |
| detector SHA | `4451e3f3664e3ad551926dc771e8cf4d0da9cd6648a9b841ea9d22bea86f15b3` |
| veto artifact SHA | `99377b3fc21283334f71cb998aafda61c7b379b6fd3e9c9875adb13afa7e1138` |
| mode | `replace_score` |
| veto threshold | `0.845` |
| train manifest SHA | `7bec763a5afb6bc962aaf05f39146cefbd17f569e24234111aab3f2f20390429` |
| val manifest SHA | `880dc3416efe20b29d4d0fc48f4063b3f5f1ef6e34267d16c1773063eb169917` |

## Metrics at freeze (val)

| | V2 | V3-1 |
| --- | ---: | ---: |
| Q_D | 0.8879 | 0.9302 |
| FPR | 0.1121 | 0.0561 |
| Recall | 0.9767 | 0.9302 |

Recall cost on val is acknowledged (FN↔FP). Not validated until preregistered fresh holdout.

## Reproduce

See `v3-1-engineering-freeze.json` + manifests in this directory.
Feature extract + train scripts hashed in the JSON; do not retune.

## Next gate

NX S1 paired V2 vs V3-1 integrated latency (`delta_p95`), then stop for holdout preregistration adjudication.
