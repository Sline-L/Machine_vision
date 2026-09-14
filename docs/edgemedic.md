# EdgeMedic 与 GearPro

边缘自治运行时设计。LLM（板上 Qwen3-4B）只做复杂语义诊断，不是系统本体。

一句话：在 Orin NX 上，把不完全可靠的小模型嵌进有安全边界的运行时，使 GearPro 能感知、诊断、降级、恢复，并从故障经验中学习。

约束、等级、RQ 与原则见 Cursor 规则 `.cursor/rules/edgemedic.mdc`。

当前研究状态（机制 ≠ 能力验证）：

```text
Line 1: FROZEN / REPRODUCED
Controlled healthy baseline: COMPLETE

Healthy thermal/drift characterization: COMPLETE
Expected steady-state V5 p95: ~178–186 ms
Experiment admission gate: <190 ms, unchanged

Injector ON/HOLD/OFF qualification: NOT QUALIFIED
  compute-heavy GEMM/conv: DISQUALIFIED (GPU util is not a V5 proxy)
  alternative contention calibration: NEXT (memory bandwidth, then SM occupancy)
  triggerability / margin / sustainability: fail on v3 sweep
  reversibility: pass on v3 sweep (OFF back under 190 / into 178–186)
A3 pilot: PAUSED
A3 effectiveness: NOT ESTABLISHED
```

> A2+A3 mechanism implemented, research-level effectiveness not yet validated.

Q0–Q3 are frozen. The first A3 3+3 is **invalid for ASR/MTTR**: the injector was not qualified (GPU util ≈99% with V5 145–168 ms; Restart “success” was a 202/221 ms spike). Do not compare Restart vs SPARSE until:

```bash
python -m edgemedic.injector_qual --mode healthy-drift --duration-s 180
python -m edgemedic.injector_qual --mode sweep
python -m edgemedic.injector_qual --mode qualify --repeats 5 --kind bandwidth --bytes-mb 512 --load-ms 100 --idle-ms 0
```

Compute-heavy GEMM/conv is **disqualified** for V5 fault injection. Calibration v4 uses memory-bandwidth and SM-occupancy contention. **Selectivity** (V5 worsens, locator stable, valid_ratio high) is reported but not hard-gated until data exist. Do not use `jetson_clocks` as the official A3 environment.

Expected healthy envelope is last-60 s V5 p95 **~178–186 ms** (FULL+PT, T&lt;60 °C). Experiment **admission** stays **recent V5 p95 &lt;190 ms** plus FULL, PT, injector OFF, worker healthy, temperature in band. A 15 s window at 189.7 ms is jitter, not a failed health definition.

Injector qualification (no Restart/SPARSE) has four gates: **triggerability** (sustained ≥2 s `V5_OVERLOAD`), **margin** (HOLD V5 p95 ≥220 ms, not 201–205), **sustainability** (HOLD stays in overload, not spikes), **reversibility** (OFF returns under the 190 ms admission gate; typical band 178–186 is reported separately). **Selectivity** is observational: target `V5_OVERLOAD`, not `SYSTEM_OVERLOAD`. Sweep then 5× qualify. `python -m edgemedic.a3` stays blocked until `fault_injector_qualified=true`. If OFF stays at 190+, debug injector cleanup — do not start 3+3.

Baseline tag：`edgemedic-a2a3-mechanism-baseline`。A4、CLASSIFY_ONLY / LOCATE_ONLY 仍不在范围。测量文档：[architecture](edgemedic-architecture.md)、[verification](edgemedic-verification.md)、[benchmark](edgemedic-benchmark.md)、[experiments](edgemedic-experiments.md)、[model bundle](model-bundle.md)。

| 协议 | 文档 | JSON Schema |
| --- | --- | --- |
| SystemSnapshot v1 | [edgemedic-system-snapshot-v1.md](edgemedic-system-snapshot-v1.md) | [edgemedic/system-snapshot.schema.json](edgemedic/system-snapshot.schema.json) |
| InferenceProfile v1 | [edgemedic-inference-profile-v1.md](edgemedic-inference-profile-v1.md) | [edgemedic/inference-profile.schema.json](edgemedic/inference-profile.schema.json) |
| Action Schema v1 | [edgemedic-action-schema-v1.md](edgemedic-action-schema-v1.md) | [edgemedic/action.schema.json](edgemedic/action.schema.json) |
| Runtime Bundle v1 | [model-bundle.md](model-bundle.md) | [edgemedic/runtime-bundle.schema.json](edgemedic/runtime-bundle.schema.json) |
| Guardian / Reflex v1 | [edgemedic-guardian-reflex-v1.md](edgemedic-guardian-reflex-v1.md) | 确定性规则，无独立 schema |
| Architecture / RQ status | [edgemedic-architecture.md](edgemedic-architecture.md) | 机制 vs 实验验证 |
| Verification | [edgemedic-verification.md](edgemedic-verification.md) | config/function/mission、LKG |
| Bench | [edgemedic-benchmark.md](edgemedic-benchmark.md) | EdgeMedicBench |
| Experiments | [edgemedic-experiments.md](edgemedic-experiments.md) | runner、ASR/MTTR 口径 |

实现顺序：帧时间戳与阶段耗时 → Camera 与 Qt 解耦 → Snapshot → Profile → Control API → Guardian/Reflex → 再接 Qwen。第一里程碑是 **不跑 LLM 也能观察、降级、验证动作**。
