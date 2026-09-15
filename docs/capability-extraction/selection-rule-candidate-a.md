# Candidate A — validation threshold selection rule (frozen before compute)

**Status:** rule locked **before** any Candidate A threshold calculation.  
**Split:** Scratch V5 **validation only** (`dataset_defects/images/val_scratch`).  
**Forbidden:** any access to `test_scratch` for selection or retune.

Source: `Machine_vision_dataset` / `origin/dataset` `train_scratch_v5.py`  
(`choose_threshold`, `PRIMARY_FPR_CAP`, fusion winner `default_threshold` assignment).

## Constants (verbatim from train)

```text
FPR_CAPS = (0.10, 0.20, 0.30, 0.50)
PRIMARY_FPR_CAP = 0.20
```

Post-selection **target check** (report only; does not change the chosen threshold):

```text
target_met ⇔ recall >= 0.95 AND fpr <= 0.20
```

## Candidate definition (fixed)

```text
profile:     classifier_mean / Candidate A
models:      classifier_1 + classifier_2  (bundle Scratch V5 FULL pair)
fusion:      arithmetic mean of the two temperature-calibrated scores
detector:    disabled
temperatures: from model/model2/inference_config.json (do not re-fit)
```

Score used for thresholding:

```text
p_i = mean( T1(raw_cls1_i), T2(raw_cls2_i) )
```

where \(T_k\) is the **already frozen** per-classifier temperature from the FULL bundle config.

## Selection algorithm (verbatim)

Reproduce `choose_threshold(labels, probabilities, fpr_cap=0.20)`:

1. Candidate thresholds = `{0.0, 1.0} ∪ {all validation scores p_i}`, sorted ascending.
2. For each threshold `t`, decide `predict = (p >= t)`.
3. Compute TP/FP/TN/FN, then recall / precision / FPR / F1.
4. Rank key (lexicographic, **higher is better**):

```text
key = (fpr <= 0.20, recall, -fpr, precision)
```

5. Keep the row with the maximum key. That row’s `threshold` is the freeze.

### Implications (do not “fix”)

- Feasibility under FPR≤0.20 is the **first** sort key (boolean), then maximize recall, then minimize FPR, then maximize precision.
- This is **not** “first require Recall≥0.95, then minimize FPR”. Recall≥0.95 appears only in the separate `target_met` flag after selection.
- Do not invent a new objective. Do not look at curves and then change the rule.

## Labels

Same as `prepare_scratch_v5.load_samples` for `val_scratch`:

```text
XML present in annotations/val_scratch → label = scratch (1)
else → label = normal (0)
```

Expected counts (FULL train report): **43 scratch / 107 normal / 150 total**.

## Outputs required

```text
classifier_only_mean.val-frozen.json   # runtime-facing freeze record
val_predictions.csv                    # per-image scores (analysis)
selection_trace.json                   # rule + chosen key + confusion
```

No `test_scratch` paths may appear in inputs, outputs, or logs.
