# Data split provenance (v3) — post GitHub dataset audit

## Verdict

```text
fresh formal holdout available?  NO
test_scratch:                    CONSUMED (diagnostic_only)
```

Re-audited `origin/dataset` @ `581647d` — no new Scratch holdout beyond the three documented splits.

## Scratch V5 splits

| split | n | train | val thr/select | formal inspected | fresh_holdout_candidate |
| --- | ---: | :---: | :---: | :---: | :---: |
| `train_scratch` | 364 | Y | N | N (locked) | **false** |
| `val_scratch` | 150 | N | **Y** | Y | **false** |
| `test_scratch` | 150 | N | N | **Y (FULL + classifier_only_v1)** | **false** |

## Other dataset content (not Scratch formal holdout)

| pool | why not holdout |
| --- | --- |
| `dataset_gear/images/test` | gear detection task; not Scratch Mission |
| `dataset_gear` replay pack | gear **train** frames; smoke/latency only |
| parent `images/val` leftovers | unproven exclusion from val construction |
| `gear_detection/predictions/test/*` | gear model outputs; unrelated to Scratch contract |
| auto_search pilot dirs | training artifacts / diagnostics |

## Policy for v2

All candidate selection uses **val_scratch only**.  
`test_scratch` → failure diagnosis only (already done for classifier_only_v1).  
Formal admission requires **new** independent holdout from vision/dataset owners.
