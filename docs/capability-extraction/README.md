# Capability Extraction — Scratch V5 classifier-only

Status: **extraction / design artifact only**. No GearPro profile opened. No locked `test_scratch` retune.

```text
Source of truth (vision pipeline):
  Machine_vision_dataset  (mirrored here as origin/dataset + final/)

Runtime gap (this repo):
  model/model2 = FULL weighted only
  gp/scratch_v5.py always runs detector
  CLASSIFY_ONLY implemented=False
```

## Corrected research framing

**Previous (too conservative):** wait for vision to invent a new light capability.

**Corrected:** dataset-side already has classifier-only **config semantics + inference + train-time candidates**. Missing piece is freezing one operating point into a **GearPro runtime capability / profile**, not redesigning the model stack.

Ask vision / product:

> Scratch V5 already supports classifier-only. Which pre-registered fusion + threshold do we freeze as the runtime profile, and what quality / Mission utility do you accept?

Do **not** ask: “can you build classifier-only from scratch?”

---

## Protocol evidence (dataset)

### Inference contract (`infer_scratch_v5.py`)

Config shape already general:

```json
{
  "classifiers": [...],
  "detector": null_or_object,
  "fusion": { "type": "..." },
  "default_threshold": ...
}
```

Fusion types used in code:

| `fusion.type` | needs detector? |
| --- | --- |
| `classifier` | no |
| `classifier_mean` | no |
| `classifier_max` | no |
| `weighted` | yes |
| `soft_or` | yes |

Main path: `if config.get("detector"):` then run detector.  
`detector=null` + `classifier_mean` is **legal** on the dataset infer path.

### Train candidates (`train_scratch_v5.py`)

Before detector fusion, the pipeline always builds:

```text
single classifier (each chosen model)
classifier_mean  (if ≥2 classifiers)
classifier_max   (named classifier_soft_or in candidate list)
```

Then pairs those with detector via `weighted_*_a{0.25,0.50,0.75}` and `soft_or_*`.

Winner shipped as FULL:

```text
weighted_classifier_mean_a0.25
α=0.25 · classifier_mean(EfficientNet, ResNet18) + 0.75 · P2 detector@960
val: Recall≈0.977  FPR≈0.084  thr≈0.3003
```

### Locked-test evaluator

`evaluate_scratch_v5_test.py` takes `--config`, reuses `predict_classifier` / `predict_detector` / `fuse`.  
One frozen classifier-only config → **one** locked evaluation. Do not sweep thresholds on `test_scratch`.

---

## Recovered validation operating points (committed `final/`)

From `final/leaderboard.json` (FPR cap **0.20** primary):

| name | kind | Recall | FPR | F1 | thr | meets val target (≥0.95 R, ≤0.20 FPR) |
| --- | --- | --- | --- | --- | --- | --- |
| **f_efficientnet_b0_384_w1_s20260911** | classifier | **0.9535** | **0.1215** | 0.8454 | 0.5429 | **yes** |
| p_resnet18_384_w1 | classifier | 0.9302 | 0.1402 | 0.8163 | 0.6628 | no |
| f_resnet18_384_w1_s20260911 | classifier | 0.9302 | 0.1682 | 0.7921 | 0.6267 | no |
| p_efficientnet_b0_384_w1 | classifier | 0.9302 | 0.1682 | 0.7921 | 0.3841 | no |
| other pilots | classifier | lower | — | — | — | no |

FULL winner (not classifier-only) in `final/final_report.json`:

| name | Recall | FPR | thr |
| --- | --- | --- | --- |
| weighted_classifier_mean_a0.25 | 0.9767 | 0.0841 | 0.3003 |

### Gap in committed artifacts

Train **computes** `classifier_mean` / `classifier_max` fusion rows, but committed `final/leaderboard.json` only stores base classifiers + detectors.  
**Val OP for `classifier_mean` of the two FULL classifiers is not in this repo’s `final/`.**  
Recovery options (val only, never locked test for selection):

1. Re-load dataset training run fusion_rows if still on disk in Machine_vision_dataset; or  
2. One-shot **val** rescore with `detector=null` + `fusion.type=classifier_mean` using the same temperatures/weights as FULL; freeze that thr.

Machine-readable extract:  
`docs/capability-extraction/classifier_only_val_candidates.{json,csv}`

---

## Pre-registered candidates (do not open API yet)

### Candidate A — `classifier_mean` (preferred productization shape)

```text
weights: same classifier_1.pt + classifier_2.pt already in model/model2
detector: null (do not call detector.pt)
fusion.type: classifier_mean
threshold: TBD — freeze from val (not yet in final/)
expected latency benefit: skip P2@960 forward (dominant V5 stage)
```

Why preferred: no new weights; closest to FULL’s classifier half; matches train’s formal candidate.

### Candidate B — single EfficientNet (complete frozen val OP today)

```text
models: [f_efficientnet_b0_384_w1_s20260911]  → classifier_1.pt in bundle
fusion.type: classifier
threshold: 0.542919409017341   # val FPR-cap 0.20 point from leaderboard
val: R=0.9535 FPR=0.1215 F1=0.8454  (meets train val target)
locked test: NOT RUN for this config
```

Use as fallback if mean OP cannot be recovered quickly; still one locked-test later.

### Not candidates for freeze-now

| idea | why |
| --- | --- |
| Sweep thr on `test_scratch` | locked set discipline |
| Agent imgsz/threshold invent | forbidden |
| LOCATE_ONLY | drops defect semantics |

---

## Runtime gap (GearPro)

| layer | today |
| --- | --- |
| `model/model2/manifest.json` | single FULL fusion; no `profiles` map |
| `gp/scratch_v5.py` | requires detector dict; always runs detector |
| `gp/profiles.py` | `CLASSIFY_ONLY` `implemented=False`, \(Q_D=0.65\) placeholder |
| EdgeMedic | must not open until capability contract + runtime path exist |

Natural bundle extension (sketch — not implemented):

```json
{
  "bundle_id": "scratch-v5-2026-09-14",
  "profiles": {
    "full": { "...": "current weighted" },
    "classifier_only": {
      "fusion": { "type": "classifier_mean", "models": ["..."] },
      "detector": null,
      "default_threshold": "FROZEN_FROM_VAL",
      "quality": "TBD_BY_VISION_MISSION"
    }
  }
}
```

---

## Still blocked (policy, not invention)

```text
expected_Q_D / minimum_Mission_utility
```

Placeholder \(Q_D=0.65 → U≈0.825 < 0.85\) remains a **Mission semantics** decision. Do not lower floors so A3 passes.

Also blocked until (after latency pretest passes):

1. Choose A vs B (or vision-named id)  
2. Freeze val thr for that config  
3. Mission \(Q_D\) / utility acceptance  
4. Optional: **one** locked `test_scratch` with that config  

---

## Ordered next steps (do not cross)

```text
Primary A: BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY
classifier_only_v1: REJECTED BY LOCKED MISSION CONTRACT
CLASSIFY_ONLY: NOT IMPLEMENTED
Secondary B: READY FOR FORMAL STUDY
```

Verdict: [primary-a-verdict.md](primary-a-verdict.md)
