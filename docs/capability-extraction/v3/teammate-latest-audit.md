# Teammate latest vision update audit

Audit source: `Sline-L/Machine_vision_dataset` **main** @ GitHub (not stale `origin/dataset` mirror).

## Sync summary

| item | value |
| --- | --- |
| repo | `https://github.com/Sline-L/Machine_vision_dataset` |
| branch | `main` |
| latest commit | `dca030654eefd84e15b0bf16a391e1affc17af0b` |
| commit time | `2026-09-13T23:43:46Z` |
| previously known baseline | GearPro `origin/dataset` @ `581647de462256c40d357d9fc4a3d1f6061023b0` (2026-09-12) |

### Delta vs old baseline

Old mirror had Scratch V5 scripts/outputs only. **Main adds:**

```text
train_missing_hole_v1.py
train_unified_defect_v1.py
evaluate_missing_hole_v1_test.py
missing_hole_runtime.py
infer_gear_defects.py
outputs/missing_hole_v1/
outputs/unified_defect_v1/
docs/missing_hole_v1/
dataset_defects/missing_hole_v1/
```

Weights under `outputs/*/final/*.pt` are **Git LFS pointers** (~133 B) on GitHub; full binaries require `git lfs pull`. GearPro `model/model2/` still holds production Scratch V5 weights only.

Local audit clone: `G:/CODE/Machine_vision_dataset_audit` (sparse metadata via GitHub API; full clone in progress for LFS).

---

## B. unified_defect_v1 audit

### Artifacts located

| artifact | path | status |
| --- | --- | --- |
| training | `train_unified_defect_v1.py` | present |
| inference runtime | reuses `missing_hole_runtime.py` + `train_scratch_v5.build_network` | present |
| evaluation | val-only in training script; no standalone test script | val complete |
| outputs | `outputs/unified_defect_v1/` | present |
| leaderboard | `leaderboard.json` | 5 candidates |
| final weights | `final/unified_classifier.pt` | LFS pointer |
| inference config | `inference_config.json` | frozen |
| docs | `docs/missing_hole_v1/统一模型实验.md` | present |

### Ten audit questions

| # | question | answer |
| --- | --- | --- |
| 1 | Training complete? | **YES** — leaderboard + config + final weight path written |
| 2 | Frozen runnable weights? | **PARTIAL** — config complete; weight is LFS on GitHub, not in GearPro bundle |
| 3 | Primary model? | `joint_cls_efficientnet_b0_512` → shipped as `unified_classifier.pt` |
| 4 | Input size? | **512** |
| 5 | Classifier / detector structure? | **Single EfficientNet-B0 classifier only** (detector candidates trained but not selected) |
| 6 | Val metrics @ FPR≤0.20? | Recall **0.9434**, FPR **0.1667**, Precision **0.9259**, F1 **0.9346**, Q_D **0.8333** |
| 7 | Threshold rule? | Same as missing-hole pipeline: val FPR cap then max recall (`rank_key` in `train_missing_hole_v1.py`) → **0.6764997972601763** |
| 8 | Test used for selection? | Config claims `test_used: false`; **verified no files under `outputs/unified_defect_v1/test/`** |
| 9 | Fresh independent holdout? | **NO** for GearPro Scratch admission |
| 10 | Runtime/inference config? | **YES** — `inference_config.json` |

### test_used cross-check (do not trust field alone)

| evidence | finding |
| --- | --- |
| `outputs/unified_defect_v1/` | no test predictions |
| `train_unified_defect_v1.py` | explicitly writes `test_used: False`; experiment docs say test not read |
| `outputs/missing_hole_v1/test/test_report.json` | **diagnostic** `unified_single_model` block on locked `test_missing_tooth` (150 imgs) — predictions consumed for comparison, **not** for unified threshold/model selection |
| `test_scratch` | separate split; consumed by GearPro locked eval |

**Conclusion:** unified model was **not** selected on test, but the same locked missing-hole test was used once for diagnostic OR-comparison. That test is **not** a fresh holdout for unified formal admission.

### Dataset / split (joint)

```text
Joint reliable set: 437 images (285 defect, 152 normal)
  - 364 fully supervised scratch+missing
  - 73 extra missing_hole positives
  - 59 scratch-unknown negatives excluded
Val: 77 images (53 pos, 24 neg) — joint scratch OR missing_hole label
Seed: 20260913, group-stratified, no cross-split near-dupes
```

---

## C. Missing Hole V1 audit

### Artifacts

| artifact | path |
| --- | --- |
| training | `train_missing_hole_v1.py` |
| test eval | `evaluate_missing_hole_v1_test.py` |
| runtime | `missing_hole_runtime.py` |
| outputs | `outputs/missing_hole_v1/` |
| final report | `docs/missing_hole_v1/FINAL_REPORT.md` |

### Task semantics

```text
Binary missing_hole / gap defect on cropped gear ROI
NOT Scratch-only; separate specialist pipeline
Production fusion: cls1(EffNet512) + cls2(ResNet384) mean + detector(std960) @ α=0.5
Gear-level OR with Scratch V5 via infer_gear_defects.py (inventory only for GearPro)
```

| field | value |
| --- | --- |
| val (frozen threshold) | R=1.0000, FPR=0.0615, P=0.8947 |
| locked test (150 imgs, 2026-09-13) | R=0.8182, FPR=0.0377, P=0.9000 — **target R≥0.95 NOT met** |
| weights | `classifier_1.pt`, `classifier_2.pt`, `detector_3.pt` (LFS) |
| latency note | ~66.5 MB bundle; README suggests classifier-first gating as future work |
| frozen operating point | threshold **0.3413327979078584** in `inference_config.json` |
| test status | **CONSUMED** — `evaluation_lock.json` + `test_report.json` |

**Do not merge into GearPro Scratch V5 runtime without explicit mission approval.**

---

## D. Mission semantics

| model | verdict label | GearPro Scratch mission |
| --- | --- | --- |
| Scratch V5 FULL | scratch → DEFECT | **exact** |
| classifier_only_v1 | scratch → DEFECT | exact (but locked FAIL) |
| effnet + det v2 | scratch → DEFECT | **exact** |
| Missing Hole V1 | missing_hole → DEFECT | **incompatible** (different defect) |
| unified_defect_v1 | scratch **OR** missing_hole → DEFECT | **superset** |

### Superset impact

> Would a GOOD (non-scratch) image with only missing_hole become DEFECT under unified?

**YES.** Unified positive label is `int(scratch or missing)`. Normal gear with missing hole but no scratch would be DEFECT under unified, while current GearPro Mission is Scratch binary verdict only.

```text
semantic_compatibility: superset
→ Mission semantics change; cannot enter GearPro runtime without approval
```

Combined-system test (diagnostic, consumed): unified single model any-defect R=0.7606, FPR=0.4177 vs specialist OR R=0.8873, FPR=0.2278. Teammate explicitly recommends **keeping dual specialists**, not unified, for production.

---

## E. unified_classifier as lightweight candidate

| metric | FULL Scratch V5 | classifier_only_v1 | unified_classifier |
| --- | --- | --- | --- |
| semantics | scratch | scratch | scratch∨missing_hole |
| Q_D,val | 0.9159 | 0.9065 (val only) | 0.8333 (joint val) |
| locked / test | test_scratch consumed | locked FAIL | diagnostic on test_missing_tooth: Q_D≈0.58 |
| NX p95 | 246 ms | ~58 ms | **not probed** (weights LFS) |
| model size | ~130 MB w/ MH | ~30 MB | ~15.6 MB (teammate report) |
| detector | yes | no | no |

**Not promoted to PRIMARY_V2_CANDIDATE** because:

1. Mission superset — not Scratch A3 recovery profile.  
2. Joint val ≠ Scratch val; lower Q_D than effnet+det on Scratch val.  
3. Diagnostic combined test already shows weak generalization vs specialist OR.  
4. No fresh holdout; weights not in GearPro bundle.  
5. Same classifier-only structural risk that failed locked Scratch eval.

---

## G. Data lineage / holdout map

| split | images | used for training | used for val/threshold | used for selection | consumed predictions |
| --- | ---: | --- | --- | --- | --- |
| scratch train/val | per scratch_v5 | yes | yes | yes | — |
| test_scratch | 150 | no | no | no (GearPro locked) | **YES — GearPro** |
| missing_hole train/val | 397/99 | yes | yes | yes | — |
| test_missing_tooth | 150 | no | no | no (MH one-shot) | **YES — 2026-09-13** |
| unified joint val | 77 | no (held out) | yes | yes (unified only) | — |
| unified formal holdout | — | — | — | — | **NONE sealed** |

```text
fresh_holdout_for_GearPro_Scratch_capability: NO
fresh_holdout_for_unified_classifier: NO (diagnostic test overlap)
```

---

## I. Maturity gate

| pipeline | weights | config | val | fresh holdout | Scratch-compatible | formal capability |
| --- | --- | --- | --- | --- | --- | --- |
| unified_defect_v1 | LFS | yes | yes | no | **no (superset)** | incomplete |
| Missing Hole V1 | LFS | yes | yes | test consumed | no | complete for MH mission, not GearPro |
| effnet+det v2 (GearPro exploratory) | in GearPro | draft | yes | no | yes | blocked on holdout |

**Do not start new vision training** until holdout sealed; teammate artifacts already answer “classifier-only lightweight” for joint defects — **insufficient for Scratch locked mission**.

---

## Audit verdict

```text
B. TEAMMATE PRODUCED USEFUL COMPONENTS,
   BUT FORMAL CAPABILITY STILL INCOMPLETE
```

Useful: Missing Hole specialist stack, unified experiment confirming single-classifier limits, runtime helpers, richer provenance.

Not ready: GearPro A3 Scratch lightweight admission — still `latency_degraded_v2_effnet_det` exploratory primary, formal blocked on fresh holdout.
