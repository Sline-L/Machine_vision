# EdgeMedic 与 GearPro

边缘自治运行时设计。LLM（板上 Qwen3-4B）只做复杂语义诊断，不是系统本体。

一句话：在 Orin NX 上，把不完全可靠的小模型嵌进有安全边界的运行时，使 GearPro 能感知、诊断、降级、恢复，并从故障经验中学习。

约束、等级、RQ 与原则见 Cursor 规则 `.cursor/rules/edgemedic.mdc`。

## Phase seal — measurement baseline + capability admission

```text
measurement tag:  edgemedic-a2a3-measurement-baseline → 7c346fd
stable branch:    srtp-web
```

> Agent/runtime already has the full framework to admit, constrain, and verify a
> lightweight capability. The blocker is no longer runtime — vision must deliver
> a new Mission-passing lightweight capability.
>
> You are no longer waiting for “Agent to be finished”; you are waiting for a
> lightweight vision capability worth the Agent safely scheduling.

Tag semantics (**not** “A2/A3 validated”):

```text
Line 1 — REPRODUCED
A3 measurement infrastructure — COMPLETE
Current A3 strategies — CHARACTERIZED
A3 effectiveness — NOT ESTABLISHED
```

Technical status:

```text
Agent/runtime architecture          COMPLETE
Line 1 containment                  COMPLETE / REPRODUCED
Measurement infrastructure          COMPLETE

Capability admission framework      ON MAINLINE (fail-closed registry)
Existing lightweight search         EXHAUSTED
classifier_only_v1                  REJECTED
Fresh formal holdout                MISSING
Vision redesign                     REQUIRED

A3 runtime readiness                HIGH
A3 usable recovery capability       MISSING
A3 effectiveness                    NOT ESTABLISHED
```

Primary A reopen trigger:

```text
vision capability v2 arrives
AND
new independent holdout exists
```

Then: `val freeze → latency → contract → fresh locked → registry → runtime → NX → pressure A3`.
Interface for vision: [vision-redesign-interface.md](capability-extraction/v2/vision-redesign-interface.md).
Registry review: [integration-capability-registry-review.md](integration-capability-registry-review.md).

Exploration leftovers stay on `experiment/lightweight-capability-v2` (Pareto / failure analysis).

## Research status (mechanism ≠ effectiveness)

```text
Line 1 — REPRODUCED

A3 strategy study
Restart baseline      CHARACTERIZED
SPARSE latency        NOT SUPPORTED
SPARSE capacity       NOT SUPPORTED
classifier_only_v1    RUNTIME REJECTED BY MISSION CONTRACT

Primary A
BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY
  (VISION REDESIGN REQUIRED; frozen-artifact search exhausted)

A3 effectiveness
NOT ESTABLISHED

Injector: QUALIFIED (multi_bandwidth × replicas=3)
Mission thresholds: UNCHANGED
test_scratch: consumed (diagnostic only)
CLASSIFY_ONLY: NOT IMPLEMENTED
Capability registry: fail-closed (implemented ∧ mission_approved)
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

> A2+A3 **mechanism** implemented; research-level **effectiveness** not yet validated.
> `edgemedic-a2a3-measurement-baseline` is a measurement baseline, not an A3 effectiveness baseline.

Waiting state:

```text
Agent/runtime architecture        COMPLETE
Line 1 evidence                   COMPLETE
A3 measurement infrastructure     COMPLETE
Current A3 strategies             CHARACTERIZED
Acceptable lightweight capability MISSING
Production-line validation        FUTURE
```

Q0–Q3 frozen. Pre-measurement tip `a4546e0` retired as prior baseline (history kept).
Earlier mechanism tag `edgemedic-a2a3-mechanism-baseline` remains historical.
A4、CLASSIFY_ONLY / LOCATE_ONLY 仍不在范围。测量文档：[architecture](edgemedic-architecture.md)、[verification](edgemedic-verification.md)、[benchmark](edgemedic-benchmark.md)、[experiments](edgemedic-experiments.md)、[model bundle](model-bundle.md)。

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
