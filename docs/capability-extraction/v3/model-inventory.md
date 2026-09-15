# Model inventory (v3) — GitHub + GearPro artifacts

Audit date: 2026-09-15  
Sources: `srtp-web` @ `cfdbbe8`, `origin/dataset` @ `581647d`, `Machine_vision_dataset/main` @ `dca0306`, NX probe.  
Teammate detail: [teammate-latest-audit.md](teammate-latest-audit.md).

## GitHub dataset branch (`origin/dataset`)

Latest commit:

```text
581647d data(dataset): add dataset branch contents
```

Shipped in git (not local `runs/`):

| artifact | path | role |
| --- | --- | --- |
| YOLO26n detector base | `yolo26n.pt` | scratch_v5 detector init |
| YOLO26n-cls | `yolo26n-cls.pt` | pilot classifier family |
| Scratch splits | `dataset_defects/images/{train,val,test}_scratch` | train/val/locked test |
| Train/eval scripts | `train_scratch_v5.py`, `infer_scratch_v5.py`, `evaluate_scratch_v5_test.py` | fusion + threshold |
| Auto-search configs | `dataset_defects/auto_search_v3/detectors/*` | pilot detector variants (weights not in git) |

**Not in git:** `runs/scratch_v5/**/best.pt` (leaderboard paths point to historical Windows `DATASET/runs/`).

## GearPro bundle (runtime)

| artifact | architecture | input | SHA256 (manifest) | val @ FPR≤0.20 | runtime |
| --- | --- | ---: | --- | --- | --- |
| `classifier_1.pt` | EfficientNet-B0 | 384 | `44461f4e…` | R=0.9535 FPR=0.1215 | FULL + probes |
| `classifier_2.pt` | ResNet18 | 384 | `d07678a6…` | R=0.9302 FPR=0.1402 | FULL + probes |
| `detector.pt` | YOLO P2 | 960 | `4451e3f3…` | det-only R=0.8837 | FULL |
| `model1.pt` | YOLO locator | — | — | gear task | FULL |

Mirror copies: `final/{classifier_1,classifier_2,detector}.pt` (same bundle family).

## Leaderboard-only pilots (weights absent from GearPro)

From `final/leaderboard.json` — paths under external `runs/scratch_v5/`:

| name | kind | val @0.2 cap | notes |
| --- | --- | --- | --- |
| `p_detector_standard_960` | detector | R=0.884 FPR=0.196 | lighter arch? weights not shipped |
| `p_detector_p2_960` | detector | same as bundle det | production winner |
| pilot classifiers 512 / yolo_cls | classifier | mostly fail R≥0.95 | not in bundle |

## TensorRT

`model/model1/model1.engine` — optional locator fast path; not required for Scratch v2 design.

## Teammate upstream (`Machine_vision_dataset/main` @ `dca0306`)

| artifact | architecture | input | role | val @ FPR≤0.20 | runtime |
| --- | --- | ---: | --- | --- | --- |
| `unified_classifier.pt` | EffNet-B0 | 512 | scratch∨missing_hole binary | R=0.943 FPR=0.167 Q_D=0.833 | LFS only; **superset** |
| `missing_hole_v1/final/classifier_1.pt` | EffNet-B0 | 512 | missing_hole specialist | R=1.000 FPR=0.092 | LFS; inventory |
| `missing_hole_v1/final/classifier_2.pt` | ResNet18 | 384 | missing_hole specialist | (fusion) | LFS; inventory |
| `missing_hole_v1/final/detector_3.pt` | YOLO std | 960 | missing_hole specialist | R=0.971 FPR=0.092 | LFS; inventory |

Missing Hole fusion val: R=1.000, FPR=0.0615. Locked test: R=0.818, FPR=0.038 (target not met).

## Runtime status summary

| path | status |
| --- | --- |
| FULL weighted α=0.25 | **production** |
| classifier_only_v1 | **REJECTED** (registry) |
| CLASSIFY_ONLY profile | **not implemented** |
| v2 effnet+det (proposed) | **design only** — not in runtime |
| unified_classifier (teammate) | **inventory** — Mission superset; not GearPro profile |
| Missing Hole V1 (teammate) | **inventory** — separate mission; test consumed |
