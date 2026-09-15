# Autonomous LATENCY_DEGRADED_V2 runtime — status

```text
LATENCY_DEGRADED_V2
ENGINEERING IMPLEMENTATION COMPLETE
ARTIFACT VALIDATION                 PASS
RUNTIME SWITCH / VERIFY / ROLLBACK  PASS (config + topology; NX integrated latency pending)
REGISTRY
  implemented=true
  mission_approved=false
  available=false
FORMAL EVALUATION PIPELINE          READY
PRIMARY A
  ENGINEERING READY
  FORMAL ADMISSION BLOCKED ON FRESH HOLDOUT
A3 effectiveness                    NOT ESTABLISHED
```

## Git

| item | value |
| --- | --- |
| branch | `integration/latency-degraded-v2-runtime` |
| worktree | `G:/CODE/Machine_vision-ldv2-runtime` |
| base HEAD | `cfdbbe8` (`srtp-web`) |
| backup | `backup/pre-latency-degraded-v2-runtime-20260915-145742` |
| push | see tip after session commits |

## Frozen candidate

| field | value |
| --- | --- |
| profile | `LATENCY_DEGRADED_V2` (`latency_degraded_v2_effnet_det`) |
| classifier | EffNet-B0@384 `classifier_1.pt` SHA `44461f4e…` |
| detector | P2@960 `detector.pt` SHA `4451e3f3…` |
| fusion | weighted α=0.25, `classifier_single` |
| threshold | `0.2653394325872992` |
| config_hash | see frozen JSON |
| Q_D,val / U_val | 0.8879 / 0.9439 (exploratory) |
| NX experimental p95 | 85.9 ms vs FULL 246.4 ms (pre-integration probe) |
| NX integrated p95 | **wall 129.5 ms** vs FULL **189.1 ms** (0.69×); stage 125.1 vs 186.8 (0.67×); n=40 crops |
| formal_holdout_status | MISSING |
| frozen path | `docs/capability-extraction/v3/latency_degraded_v2_effnet_det.frozen.json` |
| runtime config | `model/model2/profiles/latency_degraded_v2/inference_config.json` |

## Runtime

| item | status |
| --- | --- |
| implemented | yes — named profile + Scratch topology switch |
| warmup | via existing `rebuild_inspector` → worker reload |
| function/mission verify | existing verify pipeline; engineering markers required |
| rollback | restores previous locator/model2/threshold; crash recover → FULL if unapproved |
| provenance | `state()["capability_runtime"]` + scratch identity match flags |

## Registry

```text
implemented = true
mission_approved = false
available = false
```

No special-case `if profile == LATENCY_DEGRADED_V2: allow()`.

## Tests

| test | result |
| --- | --- |
| FULL startup | PASS |
| SPARSE startup | PASS |
| V2 production request rejected | PASS |
| V2 engineering harness load | PASS |
| bad classifier SHA reject | PASS |
| bad detector SHA reject | PASS |
| missing artifact reject | PASS |
| FULL→V2→FULL topology | PASS |
| V2→SPARSE restores FULL Scratch | PASS |
| registry/state availability | PASS |
| holdout seal/validate | PASS |
| formal one-shot lock | PASS |
| NX integrated latency | PASS — wall p95 129.5 vs FULL 189.1 (0.69×); ENGINEERING ONLY |
| pressure engineering pilot | NOT RUN |
| 10–20× leak loop / 30–60 min soak | NOT RUN |

Evidence: `python -m unittest tests.test_latency_degraded_v2` + `python tools/test_latency_degraded_v2.py`.

## Integrated latency

```text
ENGINEERING ONLY — NOT MISSION APPROVED
probe: integrated_scratch_runtime_v2 (ScratchV5Runtime FULL vs V2)
n_crops: 40  (tests/replay frames)
production_rejected: true

FULL wall p95:                  189.1 ms
LATENCY_DEGRADED_V2 wall p95:   129.5 ms   (0.69×)
FULL stage_sum p95:             186.8 ms
V2 stage_sum p95:               125.1 ms   (0.67×)
V2 cls2_p95:                    0.0 ms     (topology confirmed)
```

Artifact: `results/latency_degraded_v2/integrated_latency_nx.json`  
Experimental evaluator (85.9 ms) remains a lower bound; integrated runtime includes real overhead and must be the planning number.

## Engineering pilot

```text
NOT RUN — NOT FORMAL A3 EFFECTIVENESS
```

## Formal evaluation infrastructure

| item | ready? |
| --- | --- |
| holdout schema | yes |
| seal | yes (`tools/holdout/seal_holdout.py`) |
| candidate hash check | yes |
| one-shot lock | yes |
| formal evaluator | yes (`tools/holdout/formal_evaluate_capability.py`) |
| admission_proposal (no auto registry) | yes |

## Blocking item

```text
ONLY FORMAL BLOCKER:
FRESH SCRATCH-ONLY HOLDOUT
```

## Next (after data)

```text
seal holdout
→ preregister
→ one-shot formal_evaluate_capability
→ if mission_contract_pass
→ explicit registry mission_approved=true
→ NX smoke FULL↔V2
→ Primary A formal pilot
```
