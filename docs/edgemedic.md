# EdgeMedic 与 GearPro

边缘自治运行时设计。LLM（板上 Qwen3-4B）只做复杂语义诊断，不是系统本体。

一句话：在 Orin NX 上，把不完全可靠的小模型嵌进有安全边界的运行时，使 GearPro 能感知、诊断、降级、恢复，并从故障经验中学习。

约束、等级、RQ 与原则见 Cursor 规则 `.cursor/rules/edgemedic.mdc`。

当前研究状态（机制 ≠ 能力验证）：

```text
Line 1  Reasoner Reliability & Containment   FROZEN, REPRODUCED
  clean checkout 2c79075   results/repro_2c79075/{q0,q1,q2,q3}.json

Line 2  Runtime Recovery Effectiveness
  Stage C controlled healthy baseline   COMPLETE
  Real-resource-pressure injector       NOT QUALIFIED
  A3 pilot                              FAILED PRECONDITION / INVALID FOR EFFECTIVENESS
  Restart-only vs SPARSE                PAUSED
  A3 effectiveness                      NOT ESTABLISHED
```

> A2+A3 mechanism implemented, research-level effectiveness not yet validated.

Q0–Q3 are frozen. The first A3 3+3 is **invalid for ASR/MTTR**: the injector was not qualified (GPU util ≈99% with V5 145–168 ms; Restart “success” was a 202/221 ms spike). Do not compare Restart vs SPARSE until:

```bash
python -m edgemedic.injector_qual --mode healthy-drift --duration-s 180
python -m edgemedic.injector_qual --mode sweep
python -m edgemedic.injector_qual --mode qualify --repeats 5 --kind gemm --load-ms 80 --idle-ms 20
```

Qualification requires repeatable (5 consecutive), sustained (≥2 s overload and fault V5 p95 ≥230 ms), and reversible (settle back to that cycle’s healthy p95 + 8 ms). Do not raise the 190 ms reset bar from a failed pilot. `python -m edgemedic.a3` stays blocked until `results/injector_qual/summary.json` has `fault_injector_qualified=true`.

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
