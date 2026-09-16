# Live three-arm smoke (train/val only)

```text
NOT HOLDOUT
NOT VALIDATION
NOT development metrics
fresh_holdout: UNTOUCHED
```

| item | value |
| --- | --- |
| candidate_commit | `e8b2b0fda2af2c9c8c697d4655d527947381377a` |
| adjudicator_commit (tooling) | `c1dbaa0c40c71eb9378ff71cc319e165a68df312` |
| n | 4 (2 train_scratch + 2 val_scratch from freeze manifests) |
| schema_ok | true |
| FULL threshold | 0.300273610279458 |
| V2 threshold | 0.2653394325872992 |
| V3-1 threshold | 0.845 |
| replace_score | Mode A: `p >= 0.845` replaces V2 fused decision |

Pipeline exercised: image → FULL `ScratchV5Runtime.predict` → V2 `predict` → V3-1 `backbone_features` + frozen logistic. V2 fused vs `predict.defect_score` delta = 0 on all four crops.
