# A3 strategy matrix — closed study

Status: **mechanism study closed** for strategies available under the present runtime.
Not an A3 effectiveness claim. Do not invent new Agent A3 actions until a new
mission-grade lightweight vision capability exists.

## One-line mechanism conclusion

> **Current SPARSE is neither a per-inference latency recovery mechanism nor an
> effective capacity-shedding mechanism under the present
> `LatestFrame + single-worker` runtime.**

This is a structural result, not a tuning failure:

```text
inspect_wall ≈ 170–300 ms
FULL interval = 100 ms
SPARSE interval = 200 ms
```

Cadence is a weak capacity knob: FULL is already wall-time limited; raising the
nominal interval to 200 ms does not materially change offered service capacity.
Raising input FPS only increases LatestFrame overwrite, not queued internal work.

```text
SPARSE
├─ latency recovery: NOT SUPPORTED
├─ capacity shedding: NOT SUPPORTED
└─ mechanism: cadence-only degradation
```

## Strategy matrix

| Strategy | Mechanism | Latency overload | Capacity pressure | Verdict |
| --- | --- | --- | --- | --- |
| Restart | restart same workload | no sustained-pressure recovery | no advantage characterized | baseline |
| SPARSE | cadence 0.10→0.20 s | **Not supported** | **Not supported** | retain as cadence degradation; **not** core recovery |
| `classifier_only_v1` | skip detector / lower per-call V5 work | latency feasibility **PASS** | not admitted to runtime | **rejected by locked Mission contract** |
| future lightweight profile | truly reduce per-inspection cost | pending | pending | **blocked on vision capability** |

## Compressed research state

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
```

## What remains blocked

Only one research blocker for reopening A3 recovery experiments:

> A lightweight vision profile that **changes per-inspection workload** and
> **passes a frozen Mission capability contract** (with a fresh independent holdout).

Primary A remains the only coherent main line. Agent-side work must not invent
new A3 actions while that capability is missing.

## Reopen checklist (when vision delivers)

Reuse the existing chain; do not redesign Agent first:

```text
capability freeze
→ locked Mission contract
→ runtime profile
→ Guardian switch
→ Verify
→ real pressure experiment
```

Do **not**: retune consumed `test_scratch`, lower \(Q_D\)/U floors, reopen
`CLASSIFY_ONLY` on the rejected capability, or retune SPARSE interval / Mission
latency bars to manufacture a pass.

## Evidence pointers

| Claim | Evidence |
| --- | --- |
| SPARSE = cadence only | [a3-strategy-capability.md](a3-strategy-capability.md), session-2 status |
| SPARSE ≠ latency recovery | severe pilot Mission 0/3; Case B severity grid |
| SPARSE ≠ capacity shedding | [autonomous-secondary-b-status.md](autonomous-secondary-b-status.md) |
| input-FPS fault model invalid | LatestFrame overwrite; served rate invariant |
| `classifier_only_v1` Mission fail | [capability-extraction/primary-a-verdict.md](capability-extraction/primary-a-verdict.md) |

## Integration note

Measurement infra lives on `integration/injector-a3-measurement` @ `edcab22`.
Release review: [integration-release-review-edcab22.md](integration-release-review-edcab22.md)
(**PASS** — recommend FF into `srtp-web` + tag `edgemedic-a2a3-measurement-baseline`).
Keep failed strategies and accidental bulk artifacts on exploration branches.
Do **not** invent new Agent A3 actions while lightweight capability is missing.
