# Step 2 result — Candidate A val freeze

```text
STEP 2: COMPLETE
test_scratch accessed: false
CLASSIFY_ONLY opened: false
```

## Selection rule (locked before compute)

See [selection-rule-candidate-a.md](selection-rule-candidate-a.md).

Verbatim `train_scratch_v5.choose_threshold` with `PRIMARY_FPR_CAP = 0.20`:

```text
key = (fpr <= 0.20, recall, -fpr, precision)
```

Temperatures **not** re-fit (FULL bundle values).

## Frozen operating point

| field | value |
| --- | --- |
| `profile_id` | `classifier_only_mean_v1` |
| fusion | `classifier_mean` (cls1 + cls2) |
| detector | disabled |
| threshold | **0.5986470981744116** |
| val Recall | **0.9535** (41/43) |
| val FPR | **0.0935** (10/107) |
| val Precision | 0.8039 |
| val F1 | 0.8723 |
| confusion | TP41 FP10 TN97 FN2 |
| split | `val_scratch` (150 = 43 scratch + 107 normal) |
| `target_met` | **true** (R≥0.95 and FPR≤0.20) |
| `config_hash` | `08bd0af2c645e759d258cb90ff0f934be55ec0d7920bbbf9427c2755f588f96c` |
| dataset commit (image archive) | `581647de462256c40d357d9fc4a3d1f6061023b0` (`origin/dataset`) |

Artifacts:

```text
configs/classifier_only_mean.val-frozen.json
configs/classifier_only_mean.val_predictions.csv
configs/classifier_only_mean.selection_trace.json
```

Harness: `edgemedic/freeze_classifier_mean_val.py`

## Role assignment (after target_met)

```text
Candidate A = primary latency-degraded capability
Candidate B = fallback / alternate (EfficientNet single, thr≈0.5429)
```

A keeps both classifiers and only drops the detector (proven long-tail). B remains available if a lighter single-model path is needed later — not selected as primary.

## Next (Step 3 — contract, not coding)

Turn A/B into a formal GearPro capability contract (`Q_D` / Mission still open).  
Do **not** open `CLASSIFY_ONLY` yet.
