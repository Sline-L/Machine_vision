# A3 strategy capability: what SPARSE actually does

Status: mechanism analysis from code + docs. Not an effectiveness claim.

## Research question this document supports

> Under the same real resource-contention mechanism, as fault severity varies
> continuously, do FULL and SPARSE show systematic behavioral differences?

## FULL vs SPARSE execution path

Both profiles use the same `TwoStageInspector.inspect()` path on every accepted frame:

```text
camera/replay frame
    → Locator (YOLO .pt or .engine)
    → Scratch V5 ROI crop
         → Classifier 1
         → Classifier 2
         → P2 detector (imgsz=960)
         → fusion
    → serial / UI / snapshot
```

Source: `gp/models.py`, `gp/scratch_v5.py`, `docs/edgemedic-inference-profile-v1.md`.

### What changes on `set_inference_profile(SPARSE)`

From `gp/profiles.py`:

| field | FULL | SPARSE |
| --- | ---: | ---: |
| `inference_interval` | 0.10 s | **0.20 s** |
| `mission_quality` \(Q_D\) ceiling | 1.00 | **0.90** |
| `stop_worker` | false | false |
| locator policy | pt | **keep** (no backend swap) |
| classifiers | on | **on (unchanged)** |
| P2 detector | on, 960 | **on, 960 (unchanged)** |

**Do not confuse `mission_quality` with reported Mission Utility.**

- `mission_quality` (0.90 on SPARSE) is the profile’s **detection-quality coefficient** \(Q_D\) ceiling in `gp/profiles.py`.
- Snapshot **Mission Utility** is the aggregate
  \(U = 0.3 Q_L + 0.5 Q_D + 0.2 Q_S\) (`mission_utility()`).
- With healthy locator/serial and valid output, SPARSE therefore reports **utility ≈ 0.95**, not 0.90:
  \(0.3\cdot1 + 0.5\cdot0.9 + 0.2\cdot1 = 0.95\).

Experiment tables showing `utility 1.00 → 0.95` are the aggregate \(U\); the profile table’s `1.00 → 0.90` is \(Q_D\) only.

`apply_to_config()` only writes `config.inference_profile` and `config.inference_interval`.
It does **not** disable detector, classifiers, or change imgsz.

Worker loop (`gp/worker.py` `_inspect_camera`):

```text
read frame (new sequence only)
→ inspector.inspect(frame)     # full Locator + V5 every time
→ wait(config.inference_interval)
```

So SPARSE halves the **invocation cadence**, not the **per-call workload**.

### What does NOT change

- Per-inference Scratch V5 compute (two classifiers + detector + fusion)
- Locator model / backend (when leaving FULL with PT)
- Detector imgsz (960)
- Serial path
- Mission verify still includes a **per-inference V5 p95** bar

### Mission Verify mismatch (important)

`gp/verify.py` `mission_spec` for SPARSE:

```text
max_v5_p95_ms = 220
min_mission_utility = 0.85
min_cycles = 8 in 10 s window
```

FULL A3 window uses V5 ≤ 200 ms (`edgemedic/a3.py`).

SPARSE is designed as **rate/capacity degradation** (fewer inspections/s, slightly lower quality ceiling),
but Mission success still requires **single-inference V5 latency** under a fixed ms bar.

Therefore, under persistent bandwidth contention that raises **each** V5 call to ~250–320 ms,
SPARSE cannot satisfy a latency-based Mission criterion even if it correctly halves cadence.

This is a **mechanism / metric alignment** observation, not a license to change thresholds in this session.

## Expected measurable signatures

If SPARSE is working as implemented:

```text
cycle / inspection rate ≈ ½ of FULL   (interval 0.20 vs 0.10)
per-call V5 p50/p95 ≈ same as FULL under same fault
Mission Utility ceiling lower (0.90 vs 1.00)
valid_ratio may stay high
GPU/EMC may be slightly lower if fewer kernels are submitted
```

If FULL ≈ SPARSE on **all** of rate, latency, utility under pressure:

```text
Case C: no meaningful mitigation for this fault model
```

If latency similar but rate/utility differ:

```text
Case B: rate/capacity degradation only
```

If SPARSE latency clearly lower:

```text
Case A: unexpected (would suggest side effects or a bug)
```

## Unimplemented profiles (out of scope)

`CLASSIFY_ONLY` / `LOCATE_ONLY` remain unimplemented. Do not claim them as A3 actions.

## Severe-pressure pilot implication (already observed)

Under qualified `multi_bandwidth × 3` (V5 p95 ≈ 316–324 ms):

```text
Restart-only MISSION 0/3
SPARSE MISSION 0/3
FUNCTION 3/3 both
pressure ON throughout
```

Consistent with: SPARSE does not accelerate per-inference V5 under this fault;
Mission bars stay latency-based → Mission fails while pressure remains.

## Measured conclusion (session 2 + Secondary B)

**Case B (latency):** under `multi_bandwidth` severity S0–S5, FULL and SPARSE **per-inference V5 p95** track each other; SPARSE **inspect rate** is lower and **utility** sits at 0.95 vs 1.00.

**Capacity (Secondary B):** under `LatestFrame + single-worker`, input-FPS pressure is **INVALID**; service-capacity pressure finds **no natural P1** — FULL and SPARSE degrade together because `inspect_wall ≳ interval`.

See `docs/autonomous-session-2-status.md`, `docs/autonomous-secondary-b-status.md`, `results/a3_capability/`, `results/secondary_b/`.

Canonical closed matrix: [a3-strategy-matrix.md](a3-strategy-matrix.md).

```text
Current SPARSE is neither a per-inference latency recovery mechanism
nor an effective capacity-shedding mechanism under LatestFrame + single-worker.
```

**Route lock:** Primary A remains the only coherent A3 main line, **blocked on vision capability**. Do not retune SPARSE Mission latency bars or invent Agent A3 actions to claim success.