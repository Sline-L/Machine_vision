# V3-1 three-arm inference chain audit

```text
candidate_commit: e8b2b0fda2af2c9c8c697d4655d527947381377a
lineage: srtp-agent/v2-pressure-pilot → experiment/v3-lightweight-fp-veto
fresh_holdout: UNTOUCHED
```

Scores are **not** the same semantic quantity across arms. Formal comparison is on **binary predictions** and derived metrics, not on raw scores.

## FULL

```text
input:        BGR crop (OpenCV)
preprocessing: RGB; per-classifier square_rgb_image(imgsz=384) + ImageNet normalize
backbone:     EfficientNet-B0 (classifier_1) + ResNet18 (classifier_2) + YOLO P2 detector
score:        fused = 0.25 * mean(T(cls1), T(cls2)) + 0.75 * T(det)
              T = temperature calibration (apply_temperature)
threshold:    0.300273610279458
              source: model/model2/inference_config.json default_threshold
prediction:   score >= threshold  → scratch / REJECT
```

Implementation: `ScratchV5Runtime.predict` with `FULL_INFERENCE_CONFIG` (`gp/scratch_v5.py` `fuse_probabilities`).

## V2 (frozen LATENCY_DEGRADED_V2)

```text
input:        BGR crop
preprocessing: same square+normalize for the single EfficientNet
backbone:     EfficientNet-B0 only + YOLO P2 detector (ResNet removed)
score:        fused = 0.25 * T(cls1) + 0.75 * T(det)
              fuse_single_classifier
threshold:    0.2653394325872992
              source of truth: docs/capability-extraction/v3/latency_degraded_v2_effnet_det.frozen.json
                                field "threshold"
              cross-check: model/model2/profiles/latency_degraded_v2/inference_config.json
                           default_threshold (must match freeze)
              provenance: val choose_threshold PRIMARY_FPR_CAP=0.20
prediction:   score >= 0.2653394325872992
```

Not the generic holdout helper default. Formal tooling must call `load_v2_threshold()` from the freeze artifact.

## V3-1 (NX S1 frozen apply + replace_score)

```text
input:        same BGR crop, V2 runtime for features only
preprocessing: identical to V2 feature extract (NX S1 backbone_features)
features:     frozen 13-name ORDER from primary_veto_model.json
              cls1, det, fused_v2, n_boxes, sum_conf, mean_conf,
              top1_conf, top2_conf, top3_conf, cls_minus_det, log1p_boxes,
              raw_cls, raw_det
normalize:    (x - frozen mean) / frozen std   (artifact; no refit)
logistic:     sigmoid(clip(xs @ w + b, -30, 30))
score:        logistic probability  (REPLACE fused_v2; V2 threshold unused for V3-1 decision)
threshold:    0.845  from veto artifact
prediction:   score >= 0.845
veto_triggered (reporting): V2 prediction == 1 AND V3-1 prediction == 0
```

Development also tried Mode B (`v2_reject AND p >= gate`). **The freeze is Mode A only.** NX S1 and the formal primitive both use `score = p; reject = p >= 0.845`. `veto_triggered` is a reporting flag and does not change the decision.

## Why scores must not be pooled

| arm | score meaning | threshold |
| --- | --- | ---: |
| FULL | two-classifier fused scratch probability | 0.3003 |
| V2 | one-classifier fused scratch probability | 0.2653 |
| V3-1 | logistic P on 13 V2-derived features | 0.845 |

Adjudication uses Q_D / FPR / Recall of binary labels, not score histograms.
