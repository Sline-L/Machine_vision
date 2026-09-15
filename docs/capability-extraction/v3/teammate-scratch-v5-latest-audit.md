# Teammate Scratch V5 latest audit

```text
repo: Sline-L/Machine_vision_dataset
branch: main
audit_date: 2026-09-15
```

## Fetch result

```text
git fetch --all  (local audit clone + NX clone + GitHub API)
latest origin/main SHA: dca030654eefd84e15b0bf16a391e1affc17af0b
commit timestamp: 2026-09-13T23:43:46Z
message: Merge branch 'main' of github.com:Sline-L/Machine_vision_dataset

diff since previously audited dca0306:
(empty — tip is still dca0306)
```

No newer commits on public `origin/main` beyond the previously audited tip.
`evaluate_scratch_v5_test.py` and locked `outputs/scratch_v5/test_scratch/` artifacts are present in the audited tree at this SHA.

## Locked FULL Scratch V5 on `test_scratch`

Source artifacts (not chat numbers):

- `outputs/scratch_v5/test_scratch/test_report.json`
- `outputs/scratch_v5/test_scratch/test_predictions.csv` (recomputed)

| field | value |
| --- | ---: |
| n | 150 |
| scratch / normal | 31 / 119 |
| TP / FP / TN / FN | 25 / 20 / 99 / 6 |
| Recall | 0.8064516129032258 |
| FPR | 0.16806722689075632 |
| Specificity | 0.8319327731092436 |
| Precision | 0.5555555555555556 |
| F1 | 0.6578947368421053 |
| threshold | 0.300273610279458 |

### EdgeMedic Mission (diagnostic baseline, Q_L=Q_S=1)

```text
Q_D = min(Recall, Specificity) = 0.8064516129032258
U   = 0.5 + 0.5 * Q_D         = 0.9032258064516129
```

### Two gates (must not mix)

| gate | FULL result |
| --- | --- |
| Dataset target recall ≥ 0.95 | **FAIL** (`target_met: false` in report) |
| Dataset FPR ≤ 0.20 | PASS (0.168) |
| EdgeMedic Q_D ≥ 0.70 (QL=QS=1) | **PASS** (0.806) |

### Provenance

```text
test_scratch = CONSUMED
fresh_holdout = false
```

Reasons include at least:

- classifier_only_v1 formal/diagnostic use
- FULL Scratch V5 teammate locked evaluation (`locked_evaluation: true`)

### Generalization gap

```text
val Q_D ≈ 0.916  (teammate / prior notes)
locked test Q_D ≈ 0.806
```

FULL itself has a nontrivial validation → locked-domain gap. Do not retune FULL threshold from this.

## Weight identity vs GearPro FULL

GearPro `model/model2/inference_config.json` uses the same EffNet/ResNet/detector SHAs and threshold `0.300273610279458` as teammate Scratch V5 inference config — suitable as FULL reference for diagnostic pairing with frozen V2.
