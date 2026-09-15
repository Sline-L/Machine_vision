# V3-1 lightweight FP-veto — train/val Pareto

```text
V3-1 FP-VETO PARETO — train/val ONLY — NOT MISSION APPROVED
fresh holdout: NOT USED
test_scratch: NOT USED
```

## Baselines (V2 topology + frozen thr 0.265339…)

| split | Q_D | FPR | Recall | Mission |
| --- | ---: | ---: | ---: | --- |
| train | 0.966 | 0.004 | 0.966 | PASS |
| val | 0.888 | 0.112 | 0.977 | PASS |

## Primary selection

| field | value |
| --- | --- |
| model | `logistic_l2_1e-2` |
| mode | `replace_score` |
| threshold | 0.845 |
| val Q_D | **0.930** |
| val FPR | **0.056** |
| val recall | 0.930 |
| ΔQ_D vs V2 val | **+0.042** |
| ΔFPR vs V2 val | **−0.056** |
| Mission Q_D≥0.70 | PASS |

**Decision:** V3-1 CANDIDATE PROMISING — freeze pending NX S1 paired confirm (veto overhead ~0.005 ms).

**Next:** engineering freeze package; **do not** open fresh holdout; V3-2 not required yet.

## Latency

V3-1 adds only a tiny logistic on already-computed features; measured ~0.005 ms/call on NX CPU.  
S1 extra budget ≲10–12 ms — **budget_ok**. Integrated backbone unchanged from V2.

## Artifacts

- `features_train_val.csv`
- `primary_veto_model.json`
- `pareto_report.json`
- `veto_overhead.json`
- [v3-1-fp-veto-status.md](../v3-1-fp-veto-status.md)
