# Autonomous Secondary B session status

```text
Secondary B FAULT MODEL / MECHANISM VERDICT:
  input_arrival_pressure: INVALID
  service_capacity_pressure: PROBED — NO NATURAL P1
  Secondary B: NOT SUPPORTED (under tested models)

Canonical closure: docs/a3-strategy-matrix.md
> Current SPARSE is neither a per-inference latency recovery mechanism
> nor an effective capacity-shedding mechanism under LatestFrame + single-worker.

Primary A: BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY
A3 effectiveness: NOT ESTABLISHED
CLASSIFY_ONLY: NOT IMPLEMENTED
```

## Repo

| item | value |
| --- | --- |
| branch | `experiment/secondary-b-capacity` |
| HEAD (harness) | `f083f09` (+ docs commits if any) |
| backup | `backup/pre-secondary-b-*` (local) |
| base | `integration/injector-a3-measurement` @ `6e28fff` |
| push | `origin/experiment/secondary-b-capacity` |
| results | NX `results/secondary_b/feasibility_pilot_1/` (not overwriting old A3 dirs) |

Uncommitted Primary A docs may remain dirty locally; Secondary B code committed/pushed.

## Runtime semantics

### LatestFrame

`gp/frames.py`: only newest frame kept; publish overwrites. No backlog queue.

### FULL / SPARSE scheduler

`gp/worker.py` `_inspect_camera`:

```text
read LatestFrame
if new sequence → inspect once
wait(inference_interval)   # FULL 0.10s / SPARSE 0.20s
```

Same V5 path every inspect. Cadence gate only.

### Real inspection wall time (pilot)

```text
inspect_wall_ms p50 ≈ 170–300 ms (rises under capacity pressure)
FULL interval = 100 ms  < wall  → FULL already compute-bound / back-to-back
SPARSE interval = 200 ms ≈ wall → little intentional idle headroom
```

**Interval gate is not the primary capacity limiter** when a single inspect already exceeds 100–200 ms.

## Fault-model feasibility

### A/B/C measurement questions

| Q | Answer |
| --- | --- |
| A. Trace frame_seq / capture / start / end? | **YES** — added on `InspectionResult` + worker; probe uses same |
| B. Profile-independent demand? | **YES** — external DemandClock + optional arrival publisher |
| C. Raising pressure → measurable freshness/misses? | **Input FPS: NO** (LatestFrame). **Capacity contention: YES** (age/wall↑) but FULL≈SPARSE |

### input arrival pressure — **INVALID**

```text
arrival 5 / 15 / 30 Hz
FULL lambda_served ≈ 3.35–3.51 /s (invariant)
SPARSE lambda_served ≈ 2.59–2.67 /s (invariant)
```

Higher FPS only overwrites LatestFrame; does not increase offered inspect work after the interval+wall loop.  
`input-rate-only fault model = NOT EFFECTIVE`.

### multi-demand (native multi-ROI)

Not used as formal workload. Diagnostic-only duplication not introduced.

### service-capacity pressure — **PROBED**, no natural P1

`multi_bandwidth` replicas=2, duties 20/80 → 90/10, fixed arrival 10 Hz, FULL vs SPARSE.

| duty | FULL age_p95 | SPARSE age_p95 | FULL served | SPARSE served | FULL busy | SPARSE busy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20/80 | 350 | 355 | 3.70 | 2.62 | 0.61 | 0.47 |
| 40/60 | 356 | 355 | 3.63 | 2.63 | 0.63 | 0.47 |
| 60/40 | 386 | 374 | 3.19 | 2.40 | 0.67 | 0.51 |
| 75/25 | 408 | 398 | 2.82 | 2.22 | 0.71 | 0.55 |
| 90/10 | 455 | 406 | 2.65 | 2.26 | 0.73 | 0.54 |

Both profiles slow together. SPARSE never shows a clear region of **bounded continuity while FULL destabilizes**. Modest age edge at 90/10 is not a P1 operating region.

**Did not invent P1 by threshold fishing.**

## Metrics (definitions used)

| metric | definition |
| --- | --- |
| InspectionAge | `inspection_end_ts − source_capture_ts` (ms) |
| FrameLag | `latest_seq_at_completion − source_seq` |
| lambda_served | completed inspects / wall second |
| intentional_skip | demand during in-flight or interval gate |
| pressure_miss | eligible demand (past gate) without timely valid inspect |
| worker_busy_fraction | Σ inspect_wall / wall_time |

V5 p95 reported as **context only**, not Secondary B success gate.

## P0 / P1 / P2

```text
P0: light capacity — both relatively stable (similar ages)
P1: NO NATURAL P1 FOUND
P2: high capacity — both degrade (age↑, served↓, wall↑)
```

No controlled 5+5 comparison (protocol requires natural P1 first).

## Final verdict

```text
Secondary B: NOT SUPPORTED
```

under the tested models, because:

1. Input-rate pressure is architecturally invalid (LatestFrame).
2. Under shared capacity contention, SPARSE does not deliver a bounded continuity advantage vs FULL — inspect wall already saturates the single worker near/above the interval.

Mechanism line:

> LatestFrame + single-worker + inspect_wall ≳ interval means cadence shedding cannot create meaningful spare capacity; SPARSE lowers offered rate but does not stabilize freshness under the tested service-capacity pressure.

## Research state (frozen)

```text
Line 1: FROZEN / REPRODUCED
Primary A: BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY
classifier_only_v1: REJECTED BY LOCKED MISSION CONTRACT
Secondary B: NOT SUPPORTED (tested fault models; no natural P1)
CLASSIFY_ONLY: NOT IMPLEMENTED
A3 effectiveness: NOT ESTABLISHED
```

Pilot data: `docs/secondary-b-feasibility-pilot-summary.json`, NX `results/secondary_b/feasibility_pilot_1/`.

## Commits this session

```text
f083f09 feat(edgemedic): add Secondary B freshness telemetry and feasibility harness
```

(+ follow-up docs commit for this status file).
