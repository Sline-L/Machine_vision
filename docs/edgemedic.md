# EdgeMedic 与 GearPro

边缘自治运行时设计。LLM（板上 Qwen3-4B）只做复杂语义诊断，不是系统本体。

一句话：在 Orin NX 上，把不完全可靠的小模型嵌进有安全边界的运行时，使 GearPro 能感知、诊断、降级、恢复，并从故障经验中学习。

约束、等级、RQ 与原则见 Cursor 规则 `.cursor/rules/edgemedic.mdc`。

当前研究状态（机制 ≠ 能力验证）。A3 策略研究已收口为机制否证；正式矩阵见 [a3-strategy-matrix.md](a3-strategy-matrix.md)。

```text
Line 1 — COMPLETE / REPRODUCED

A3 strategy study
Restart baseline      CHARACTERIZED
SPARSE latency        NOT SUPPORTED
SPARSE capacity       NOT SUPPORTED
classifier_only_v1    RUNTIME REJECTED BY MISSION CONTRACT

Primary A
BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY

A3 effectiveness
NOT ESTABLISHED

Injector: QUALIFIED (multi_bandwidth × replicas=3)
Mission thresholds: UNCHANGED
test_scratch: consumed (diagnostic only)
CLASSIFY_ONLY: NOT IMPLEMENTED
```

> Current SPARSE is neither a per-inference latency recovery mechanism nor an
> effective capacity-shedding mechanism under the present
> `LatestFrame + single-worker` runtime.

Structural reason: `inspect_wall ≈ 170–300 ms` vs FULL 100 ms / SPARSE 200 ms —
cadence is not a strong capacity knob; input FPS only overwrites LatestFrame.

Retained findings:

1. Line 1 — containment works (structured decode / Guardian / Verify).
2. Degradation must match fault — SPARSE is cadence-only; not latency recovery; not effective capacity shedding here.
3. Capability contract refused fast-but-weak `classifier_only_v1`.

Do **not** invent new Agent A3 actions until a mission-grade lightweight vision
capability + fresh holdout exists. Reopen via:
`capability freeze → locked Mission contract → runtime profile → Guardian → Verify → pressure experiment`.
Do **not** retune `test_scratch`, lower \(Q_D\)/U floors, or reopen `CLASSIFY_ONLY` on the rejected capability.
Verdict: [primary-a-verdict](capability-extraction/primary-a-verdict.md); Secondary B: [autonomous-secondary-b-status](autonomous-secondary-b-status.md).

Healthy envelope / admission (unchanged):

```text
Expected steady-state V5 p95: ~178–186 ms
Admission: V5 p95 <190 + FULL + PT + injector OFF + worker healthy + temp in band
```

> A2+A3 mechanism implemented, research-level effectiveness not yet validated.

Q0–Q3 frozen. Measurement integration: `integration/injector-a3-measurement`
([integration-plan.md](integration-plan.md)). Do not bulk-merge exploration into `srtp-web`.

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
