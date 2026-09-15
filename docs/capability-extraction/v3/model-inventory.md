# Model inventory (v3) — GitHub + GearPro artifacts

Audit date: 2026-09-15  
Sources: `srtp-web` @ `cfdbbe8`, `origin/dataset` @ `581647d`, NX probe.

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

## Runtime status summary

| path | status |
| --- | --- |
| FULL weighted α=0.25 | **production** |
| classifier_only_v1 | **REJECTED** (registry) |
| CLASSIFY_ONLY profile | **not implemented** |
| v2 effnet+det (proposed) | **design only** — not in runtime |
