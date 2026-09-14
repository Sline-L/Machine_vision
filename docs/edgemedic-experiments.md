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

- `wrong_legal_action_rate` (WLAR) = wrong but whitelist-legal tool proposals / valid structured outputs (excludes abstain and illegal/unsafe tools)
- `confusion_matrix` is case → predicted label (`abstain` / `tool[:profile]`)

Q0–Q3 (**Line 1**, frozen). Paper tables use clean-checkout `results/repro_2c79075/` on HEAD `2c79075e6ccd19de0e6d49967bd195ad3d98be8f`. SCP-era JSON stays development evidence only.

Q4 state/affordance is **not** next. Line 1 is frozen. Injector is **qualified** (`multi_bandwidth×3`). Current SPARSE is **characterized as cadence degradation** and does **not** support latency-gated Mission recovery under persistent bandwidth pressure. A3 effectiveness remains **not established**. Next is a **design decision** (new latency-targeted action vs separate capacity-shedding study) — not SPARSE parameter tuning.

**Frozen Line 2 mechanism finding:** under sustained memory-bandwidth pressure, SPARSE reduces inspection cadence but leaves the per-inference V5 path unchanged; it lowers service rate without materially reducing V5 latency, so it does not restore a latency-gated Mission under persistent overload. See [a3-strategy-capability](a3-strategy-capability.md).

Qualified injector (do not retune gates):

```bash
python -m edgemedic.injector_qual --mode qualify --repeats 5 \
  --kind bandwidth --bytes-mb 512 --buffers 3 --streams 4 \
  --load-ms 100 --idle-ms 0 --matrix 128 --replicas 3
```

Capability characterization (no recovery):

```bash
python -m edgemedic.a3_capability --out results/a3_capability/severity_response
```

Gates: **triggerability** (sustained ≥2 s `V5_OVERLOAD`); **margin** (HOLD V5 p95 ≥220 ms); **sustainability** (HOLD stays overloaded, not 201 ms graze); **reversibility** (OFF → admission V5 p95 &lt;190 ms). Expected envelope 178–186 ms is descriptive. **Selectivity** is reported, not hard-gated. Do not use `jetson_clocks` for official A3. Do not change SPARSE interval / Mission V5 bars to manufacture success.

Official Line 1 provenance (same GGUF / llama.cpp for Q0–Q2; Q3 does not call the LLM):

| id | PCR / DTA / WLAR or GCR | `experiment_config_hash` | notes |
| --- | --- | --- | --- |
| Q0 `--decode prompt` | PCR 0%; DTA/WLAR N/A | `b17d27f1…1ef724` | 80 L2 calls; 41 truncated_reasoning / 20 prompt_echo / 19 prose_refusal; ~9.79 s |
| Q1 `--decode grammar` | PCR 100%; DTA 50%; WLAR 25% | `92ca9c33…e2a153` | grammar SHA `d09fe2de…83cd1e`; ~1.58 s |
| Q2 locator 110–200 ms | PCR 100%; 20/20 abstain every point | same hash as Q1 | `boundary.py` reused bench provenance (`kind=bench`); not a distinct config hash |
| Q3 `restart_worker` dry-run | GCR 100%; GAR 100%; leakage 0 | `eb90e662…5cfcf9` | `executed_any=false` |

Shared: `llama_build` `b1-41ef91f`; GGUF SHA `3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f`; `bundle_id` `scratch-v5-2026-09-14`.

Guardian claim (Q3): it rejected a syntactically valid, whitelisted `restart_worker` on a healthy worker, and approved the same tool under `WORKER_FAIL`. That is context containment, not “blocked `rm -rf`”.

```bash
python -m edgemedic.bench --reasoner qwen --runs 20 --decode prompt --out results/qwen_family_pcr.json
python -m edgemedic.bench --reasoner qwen --decode grammar --preflight
python -m edgemedic.bench --reasoner qwen --runs 20 --decode grammar --out results/qwen_family_q1.json
python -m edgemedic.boundary --runs 20 --out results/qwen_q2_boundary.json
python -m edgemedic.q3 --runs 20 --out results/qwen_q3_guardian.json
python -m edgemedic.stage_c --protocol controlled --combo full_pt --sample-s 60 --warmup-s 15 --replay-pack tests/replay
```

GCR = wrong legal actions rejected / presented. GAR = correct WORKER_FAIL restart_worker approved / presented. Overlay snapshot on Control `dry_run`; does not restart the worker.

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

3. Injector qualification (`python -m edgemedic.injector_qual`). A3 Restart vs SPARSE stays paused until `fault_injector_qualified=true`. `inject_v5_latency` is **not** this experiment.

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

## NX SIL status (controlled healthy window, not A3)

Same pack `tests/replay`, warmup 15 s, sample 60 s, `fault_mode=none`, GearPro HEAD `2c79075`. Sampler was the `--protocol controlled` script (local `a5ea663` / `/tmp/stage_c.py`) so the NX tree stayed ff-only at the Line 1 commit. `a3_claim=false`. This is a healthy continuity window, **not** Restart-only vs SPARSE.

| combo | profile | backend | cycles | valid | locator p95 | V5 p95 | total p95 | verify | utility |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| FULL + PT_SAFE | FULL | pt | 115 | 1.0 | 65.0 ms | 181.2 ms | 244.2 ms | mission | 1.0 |
| FULL + TRT_FAST | TRT_FAST | engine | 115 | 1.0 | 26.7 ms | 196.5 ms | 219.9 ms | mission | 1.0 |
| SPARSE + PT_SAFE | SPARSE | pt | 114 | 1.0 | 67.4 ms | 181.4 ms | 243.2 ms | mission | 0.95 |
| SPARSE + TRT_FAST | SPARSE | engine | 115 | 1.0 | 27.0 ms | 199.4 ms | 224.9 ms | mission | 0.95 |

FULL+TRT reached `mission` here (V5 p95 196.5 ms under the 200 ms bar). Bring-up had `function` at ~200.5 ms — do not treat that 1 ms as a backend ranking.

## Still future work

- Injector qualification (repeatable / sustained / reversible), then 3+3 A3 pilot
- Formal Restart-only vs SPARSE only after a passing pilot
- live Camera / Serial / line (Stage D)
- A4
- Missing Hole as workload expansion (not this baseline)
