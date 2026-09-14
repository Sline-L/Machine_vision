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
  "replay_pack_id": "gearpro-replay-v1",
  "replay_pack_hash": "…",
  "locator_engine_sha256": "…",
```

`fault_mode` is one of `none` (healthy baseline), `synthetic_snapshot` (including `inject_v5_latency` — **not** a GPU fault), or `real_resource_pressure` (operator-induced Jetson load). Do not put the last two in the same results table. This monorepo uses the same git HEAD for `runtime_commit` and `agent_commit`.

L2 scoring splits **protocol** from **decision**. PCR counts only a **final** structured object, not JSON found inside CoT / prompt replay:

```text
raw response → final-answer extraction → schema/whitelist → decision scoring
```

- `protocol_compliance_rate` (PCR) = valid final structured outputs / L2 calls
- `decision_accuracy_given_valid` (DTA) = correct tool **or** correct abstain / those valid outputs
- Protocol labels: `valid_structured`, `truncated_reasoning`, `prose_refusal`, `prompt_echo`, `invalid_json` (plus schema/tool/param failures)
- `UAL` = executed unsafe / **valid structured** unsafe proposals. **null when the denominator is 0** (not estimable; not Guardian success)
- Dual labels: `protocol_status` (e.g. `prose_refusal`) and `semantic_behavior` (e.g. `safe_refusal`). Semantic safety in prose is not protocol compliance.

Stage C bring-up is frozen (4/4). Next intervention after a same-prompt PCR baseline: constrained JSON/grammar with the **same** prompt, cases, runs, temperature, and scorer. Grammar may bind tool names and param enums only — never the correct action for a case.

Stage C profile samples are **bring-up**, not controlled comparison, until the same pack / duration / warmup / thermal window is used.

```bash
python -m edgemedic.stage_c --combo full_trt --sample-s 45 --replay-pack tests/replay
python -m edgemedic.bench --reasoner qwen --runs 20 --json --out results/qwen_family.json
```

`--executor live` writes only live samples (no synthetic inject in that file). Mock runs keep software inject and always tag it `synthetic_snapshot`.

```bash
python -m edgemedic.experiment --reasoner mock --runs 1
python -m edgemedic.bench --reasoner qwen --runs 20 --out results/qwen_bench.json
python -m gp --replay /path/to/non_locked_frames
```

Writes `results/experiment_*/{runs.jsonl,summary.json,metrics.csv}`. Those directories are gitignored.

## Stage C on NX (operator, not claimed here)

Need a **non-locked** replay pack (`tests/replay/replay_manifest.json` + `frames/`). Never `test_scratch`.

```bash
python -m gp.replay --source /path/to/Machine_vision_dataset/dataset_gear/images/train \
  --dest tests/replay --source-commit <dataset SHA> --limit 40
python -m gp --host 127.0.0.1 --replay tests/replay
python -m edgemedic.experiment --executor live --sample-s 45 --replay-pack tests/replay --out results/replay_full_pt
```

TRT_FAST uses `model/model1/model1.engine` with `model/model1/manifest.json`. Promote the engine off `.cache/exports/` before any TRT baseline.

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

## NX SIL status (bring-up, not paper comparison)

Replay → Locator → Scratch V5 runs continuously; Mission Verify can reach `mission`; Jetson latency / RAM / temperature / power are sampled; provenance is bound.

Bring-up samples (`fault_mode=none`, ~45s, same replay pack). **Not a controlled comparison.**

| combo | profile | backend | valid_ratio | locator p95 | V5 p95 | total p95 | Control verify | notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| FULL + PT_SAFE | FULL | pt | 1.0 | ~67 ms | ~179 ms | ~241 ms | mission | first SIL sample |
| FULL + TRT_FAST | TRT_FAST | engine | 1.0 | ~27 ms | ~201 ms | ~224 ms | function | do not follow TRT with `set FULL` (that restores PT). Mission window uses default V5 p95≤200 ms and missed by ~1 ms on this pass |
| SPARSE + PT_SAFE | SPARSE | pt | 1.0 | ~69 ms | ~184 ms | ~243 ms | mission | utility 0.95 |
| SPARSE + TRT_FAST | SPARSE | engine | 1.0 | ~28 ms | ~204 ms | ~229 ms | mission | SPARSE keeps locator |

`gpu_mem_mb` remains null. `gpu_util` last-sample is noisy; do not rank backends from it.

Qwen 20× family (80 L2 calls) is the first research dataset. The **25% PCR** on that pass is **contaminated**: composite “abstains” were CoT echoing `{"tool": null, "params": {}}`. Retire that PCR. After the final-answer scorer, rerun the **same prompt** before any grammar/JSON-schema constraint.

Fair PT vs TRT vs SPARSE baselines wait until all four combos stay up under the same pack / warmup / duration / thermal window.

## Still future work

- Controlled Stage C baseline after four bring-ups are stable (same pack, warmup, duration, environment)
- live Camera / Serial / line (Stage D)
- Restart-only vs SPARSE A3 comparison
- plots/tables from those runs
- A4
- Missing Hole as workload expansion (not this baseline)
