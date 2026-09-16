# V3-1 holdout adjudication tooling

```text
candidate_commit:    e8b2b0fda2af2c9c8c697d4655d527947381377a
adjudicator_branch:  experiment/v3-1-holdout-adjudication
tooling ≠ new model candidate
fresh_holdout:       UNTOUCHED (this package does not score it)
registry:            UNCHANGED
```

## Layout

```text
tools/v3_fp_veto/frozen_inference.py              FULL / V2 / V3-1 apply
tools/v3_fp_veto/metrics.py                       confusion + Q_D/FPR/Recall
tools/v3_fp_veto/adjudication.py                  preregistration + amendment
tools/v3_fp_veto/seal_fresh_holdout.py            scratch-holdout.v1 seal (no EDA)
tools/v3_fp_veto/formal_fresh_holdout_adjudicate.py  orchestration + lock
```

`extract_features.py` still refuses test/holdout/fresh. `train_pareto.py` is development-only and is not imported.

## Dry-run (val features, not holdout)

```text
python tools/v3_fp_veto/formal_fresh_holdout_adjudicate.py ^
  --feature-csv docs/capability-extraction/v3/v3-1-fp-veto/features_train_val.csv ^
  --split val_scratch ^
  --out-dir docs/capability-extraction/v3/v3-1-adjudication-tooling/dry-run-val-features
```

This must reproduce freeze val V3-1 counts (tp=40 fp=6 tn=101 fn=3). FULL is not scored in this mode.

## Live three-arm smoke (train/val images, not holdout)

```text
python tools/v3_fp_veto/smoke_three_arm.py
```

Integration only. Refuses test_scratch / holdout / fresh.

## Formal (do not run until READY)

Requires a sealed `scratch-holdout.v1` manifest. Writes `results/v3-1-fresh-holdout/<run-id>/` and marks that population CONSUMED. Does not mutate registry.
