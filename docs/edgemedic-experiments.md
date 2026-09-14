# EdgeMedic experiments

Status: runner **implemented, tested** on synthetic snapshots and software inject. **Not experimentally validated** on Camera/Serial/NX.

Every `summary.json` now records provenance so later model/runtime updates stay attributable:

```json
{
  "runtime_commit": "…",
  "agent_commit": "…",
  "bundle_id": "scratch-v5-2026-09-14",
  "manifest_sha256": "…",
  "reasoner": "qwen3-4b",
  "runtime_mode": "dataset_replay",
  "fault_mode": "none",
  "experiment_config_hash": "…"
}
```

`fault_mode` is one of `none` (healthy baseline), `synthetic_snapshot` (including `inject_v5_latency` — **not** a GPU fault), or `real_resource_pressure` (operator-induced Jetson load). Do not put the last two in the same results table. This monorepo uses the same git HEAD for `runtime_commit` and `agent_commit`.

`--executor live` writes only live samples (no synthetic inject in that file). Mock runs keep software inject and always tag it `synthetic_snapshot`.

```bash
python -m edgemedic.experiment --reasoner mock --runs 1
python -m edgemedic.bench --reasoner qwen --runs 20 --out results/qwen_bench.json
python -m gp --replay /path/to/non_locked_frames
```

Writes `results/experiment_*/{runs.jsonl,summary.json,metrics.csv}`. Those directories are gitignored.

## Stage C on NX (operator, not claimed here)

Need a **non-locked** image directory. Do not use `test_scratch` to retune.

1. Replay four profiles long enough to fill cycles (serial off):

```bash
python -m gp --host 127.0.0.1 --replay /path/to/non_locked_frames
# then from another shell, after inspection is running:
python -m edgemedic.experiment --executor live --sample-s 30 --out results/replay_full_pt
```

Switch locator / inference through Control (mission verify is the action response `verify_level`, not a backend string check):

```bash
python -m edgemedic.experiment --executor live --sample-s 20 \
  --live-action set_locator_profile --live-params '{"profile":"trt_fast"}'
python -m edgemedic.experiment --executor live --sample-s 20 \
  --live-action set_inference_profile --live-params '{"profile":"SPARSE"}'
```

Record from the written summary: cycle_count, valid_ratio, locator/V5/total p50/p95, GPU util/mem, RAM, temperature, power. **Do not treat a first pass as paper ASR/MTTR.**

2. Qwen3-4B bench (parallel; llama-server `:8080`):

```bash
python -m edgemedic.bench --reasoner qwen --runs 20 --json --out results/qwen_family.json
```

Read `family_table` (Known-simple / Composite / Ambiguous / Unsafe): correct_action, abstain, wrong_tool, invalid, unsafe. Stability is “same case across 20 repeats”, not a single headline score.

3. One A3 chain only, after the four-profile baseline is stable: replay FULL → **real** V5 resource pressure (`--fault-mode real_resource_pressure`) → Control `SPARSE` → continue replay → Mission Verify. Compare before / during / after SPARSE (p95, valid ratio, utility). `inject_v5_latency` stays `synthetic_snapshot` and is **not** this experiment.

`--executor live` samples a running GearPro. `--ablation no-guardian` is **mock-only**.

## Lifecycle (synthetic)

Reset snapshot → inject (optional) → detect → incident → decide → (mock execute) → collect metrics.

## Core metrics (definitions)

| metric | definition | this runner |
| --- | --- | --- |
| MTTD | `t_detect - t_fault` | synthetic detect time only |
| MTTR | `t_mission_verified - t_fault` | **null** until a live action returns `verify_level=mission` |
| ASR_function | FUNCTION_VERIFIED / injections | synthetic proxy only |
| ASR_mission | MISSION_VERIFIED / injections | not claimed |
| UAR | unnecessary **executed** recoveries / normal cases | L1 on healthy snapshots |

Resource counters (CPU/GPU/power) need Jetson telemetry on a live sample; mock runs leave them empty.

## Ablation (future recorded runs)

Full / no-L2 / no-Memory / no-Reflex / no-Guardian (mock executor). Raw-log vs Snapshot is RQ1 and is **not run yet**.

## Policy candidates

`edgemedic/candidate.py` aggregates episodes to JSON `status=candidate`. Never auto-deployed into L1. TRT_FAST stays off L1 until real PT/TRT p50/p95 exist.

## Still future work

- Stage C NX numbers for FULL/SPARSE × PT_SAFE/TRT_FAST (commands exist; results not in this tree)
- live Camera / Serial / line (Stage D)
- Restart-only vs SPARSE A3 comparison
- plots/tables from those runs
- A4
- Missing Hole as workload expansion (not this baseline)
