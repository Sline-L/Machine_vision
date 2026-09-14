# EdgeMedic 与 GearPro

边缘自治运行时设计。LLM（板上 Qwen3-4B）只做复杂语义诊断，不是系统本体。

一句话：在 Orin NX 上，把不完全可靠的小模型嵌进有安全边界的运行时，使 GearPro 能感知、诊断、降级、恢复，并从故障经验中学习。

约束、等级、RQ 与原则见 Cursor 规则 `.cursor/rules/edgemedic.mdc`。

当前研究状态（机制 ≠ 能力验证）：

```text
Line 1 — Reasoner Reliability & Containment
FROZEN / REPRODUCED

Real-resource-pressure injector
QUALIFIED
  mechanism: multi_bandwidth × replicas=3
  (compute-heavy GEMM/conv: DISQUALIFIED)

Current SPARSE strategy
CHARACTERIZED
  type: cadence degradation (interval 0.10 → 0.20)
  per-inference V5 path: unchanged

Latency-defined V5_OVERLOAD recovery
NOT SUPPORTED by current SPARSE mechanism

A3 severe-pressure pilot
  Restart-only: Mission 0/3
  SPARSE:       Mission 0/3
  FUNCTION:     3/3 both arms
  pressure ON throughout

A3 effectiveness
NOT ESTABLISHED

Next design decision (not implemented yet)
  A) redesign latency-targeted degradation action, OR
  B) open a separate throughput/capacity-shedding study for SPARSE
```

> Line 2 mechanism finding: under sustained memory-bandwidth pressure, SPARSE reduces inspection cadence but leaves the per-inference V5 computation path unchanged; it therefore does not restore a latency-gated Mission under persistent overload.

Do **not** retune Mission V5 bars or rename current SPARSE to claim latency recovery. Details: [a3-strategy-capability](a3-strategy-capability.md), [session-2 status](autonomous-session-2-status.md), [integration plan](integration-plan.md).

Healthy envelope / admission (unchanged):

```text
Expected steady-state V5 p95: ~178–186 ms
Admission: V5 p95 <190 + FULL + PT + injector OFF + worker healthy + temp in band
```

> A2+A3 mechanism implemented, research-level effectiveness not yet validated.

Q0–Q3 are frozen. Injector qualification gates and A3 Mission definitions stay frozen. Integration of measurement infrastructure: branch `integration/injector-a3-measurement` (do not bulk-merge the whole exploration branch).

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
