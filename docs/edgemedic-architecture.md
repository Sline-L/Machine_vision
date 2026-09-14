# EdgeMedic architecture

Status vocabulary used in this tree:

| label | meaning |
| --- | --- |
| implemented | code exists on `srtp-web` |
| tested | unit/synthetic tests exist |
| experimentally validated | live GearPro / NX workload numbers exist |
| future work | not this stage |

Baseline tag: `edgemedic-a2a3-mechanism-baseline`.

| capability | status |
| --- | --- |
| A0 Monitoring | implemented, tested |
| A1 Deterministic Recovery | implemented, tested |
| A2 Diagnosis mechanism | implemented, tested |
| A3 Degradation mechanism | implemented, tested |
| A2 experimental validation | future work |
| A3 experimental validation | paused: injector not qualified; first 3+3 invalid |
| A4 | out of scope |

One-line research status:

> A2+A3 mechanism implemented, research-level effectiveness not yet validated.

Do not write “A2+A3 已经实现完成” as if the research claims were proven.

EdgeMedic is a **separate process** (`python -m edgemedic`) talking only to Control API. It does not import `gp` internals and does not run shell.

```text
Unreliable Decision Source
        │
        ├── Qwen (L2)
        └── Memory
             ↓
Structured Validation (schema / JSON)
             ↓
Action Vocabulary (whitelist)
             ↓
Authority Boundary (server-assigned)
             ↓
Guardian (accept / timeout / retry)
             ↓
Precondition
             ↓
Executor
             ↓
Verify (config / function / mission)
             ↓
Rollback or LKG promote
             ↓
Mission window
```

Related: [verification](edgemedic-verification.md), [benchmark](edgemedic-benchmark.md), [experiments](edgemedic-experiments.md), [Guardian/Reflex](edgemedic-guardian-reflex-v1.md), [model bundle](model-bundle.md).

## Validation ladder

| stage | what is real | what is fake | status |
| --- | --- | --- | --- |
| A Synthetic bench | Guardian / Memory / tool choice | no models | implemented, tested |
| B Simulated runtime | verify / MTTR plumbing | cycle numbers | implemented, tested |
| C Dataset replay | locator + Scratch V5 + CUDA/Jetson telemetry on NX | frames from disk, not `/dev/video0` | Healthy 4-combo window recorded. Compute-heavy injector **disqualified**; contention calibration v4 next. First A3 3+3 invalid. `gpu_mem_mb` still null. |
| D Real camera / line | sensors, serial, conveyor | — | future work |

Replay: `python -m gp --replay <dir>` (`GEARPRO_REPLAY_DIR`). EdgeMedic still talks Control API only; it does not know whether frames came from a camera or disk. Do not replay locked `test_scratch` to retune. Do not merge the dataset repo. Missing Hole stays out of this baseline.
