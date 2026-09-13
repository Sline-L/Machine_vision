# EdgeMedic experiments

Status: runner **implemented, tested** on synthetic snapshots and software inject. **Not experimentally validated** on Camera/Serial/NX.

```bash
python -m edgemedic.experiment --reasoner mock --runs 1
python -m edgemedic.experiment --reasoner qwen --case locator_overload --runs 30
```

Writes `results/experiment_*/{runs.jsonl,summary.json,metrics.csv}`. Those directories are gitignored.

## Lifecycle (synthetic)

Reset snapshot → inject (optional) → detect → incident → decide → (mock execute) → collect metrics.

`--executor live` against a running GearPro is allowed for software inject later. `--ablation no-guardian` is **mock-only**.

## Core metrics (definitions)

| metric | definition | this runner |
| --- | --- | --- |
| MTTD | `t_detect - t_fault` | synthetic detect time only |
| MTTR | `t_mission_verified - t_fault` | **null** until live mission windows |
| ASR_function | FUNCTION_VERIFIED / injections | synthetic proxy only |
| ASR_mission | MISSION_VERIFIED / injections | not claimed |
| UAR | unnecessary **executed** recoveries / normal cases | L1 on healthy snapshots |

Resource counters (CPU/GPU/power) need Jetson telemetry on a live run; not filled here.

## Ablation (future recorded runs)

Full / no-L2 / no-Memory / no-Reflex / no-Guardian (mock executor). Raw-log vs Snapshot is RQ1 and is **not run yet**.

## Policy candidates

`edgemedic/candidate.py` aggregates episodes to JSON `status=candidate`. Never auto-deployed into L1. TRT_FAST stays off L1 until real PT/TRT p50/p95 exist.

## Still future work

- live Camera / Serial / TensorRT workload on NX
- Restart-only vs SPARSE A3 comparison
- plots/tables from those runs
- A4
