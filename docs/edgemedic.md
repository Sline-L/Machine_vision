# EdgeMedic 与 GearPro

边缘自治运行时设计。LLM（板上 Qwen3-4B）只做复杂语义诊断，不是系统本体。

一句话：在 Orin NX 上，把不完全可靠的小模型嵌进有安全边界的运行时，使 GearPro 能感知、诊断、降级、恢复，并从故障经验中学习。

约束、等级、RQ 与原则见 Cursor 规则 `.cursor/rules/edgemedic.mdc`。

当前研究状态（机制 ≠ 能力验证）：

```text
Software implementation baseline: COMPLETE
Measurement infrastructure: COMPLETE
NX software-in-the-loop: ACTIVE
Stage C bring-up: 4/4 COMPLETE (frozen; not controlled comparison)

Q0 Protocol Baseline (prompt only): FROZEN  PCR=0%  DTA=N/A  UAL=N/A
Q1 Structured Decoding (same prompt + GBNF): FROZEN
  PCR=100%  DTA=50%  WLAR=20/80 (restart_worker on unsafe_request)
  latency 9.8s → 1.57s
  paper reproduction: re-run after NX ff-only to commit 22a1410+

Q2 Decision Boundary: locator.latency_ms sweep (same grammar/prompt)
Q3 Guardian containment of wrong legal actions: NOT RUN

L2 decision effectiveness: NOT ESTABLISHED (protocol solved; decision exposed)
A2/A3 effectiveness: NOT ESTABLISHED
```

> A2+A3 mechanism implemented, research-level effectiveness not yet validated.

Structured decoding eliminated the protocol-compliance bottleneck under the tested configuration, exposing decision-quality limits. It did **not** by itself improve reasoning. Q1: composite 20/20 abstain; ambiguous 20/20 abstain; unsafe 20/20 abstain on adversarial and 20/20 `restart_worker` on `unsafe_request_01` (legal tool, wrong context). Stage C frozen. Do not change prompt or model. Next is snapshot evidence sweeps, then Guardian dry-run of wrong legal actions.

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
