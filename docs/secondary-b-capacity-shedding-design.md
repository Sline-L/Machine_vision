# Secondary B Design Review — SPARSE as capacity shedding

Status: **CLOSED — NOT SUPPORTED** under tested fault models.
See [autonomous-secondary-b-status.md](autonomous-secondary-b-status.md) and
[a3-strategy-matrix.md](a3-strategy-matrix.md). No Mission latency-gate changes.
No `CLASSIFY_ONLY`. Independent of Primary A.

```text
Secondary B — capacity shedding
READY FOR FORMAL STUDY → DESIGN OPEN

Primary A
BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY
(do not conflate with this line)
```

## Research question (formal)

> Under sustained service pressure, does reducing inspection cadence improve mission continuity and resource stability at an acceptable quality cost?

Mechanism under test:

```text
SPARSE = cadence / capacity-shedding
NOT per-inference latency recovery
```

Do **not** ask whether V5 p95 falls from ~220 → ~180. That is Primary A / latency domain.

## Separation from Primary A

| | Primary A | Secondary B |
| --- | --- | --- |
| Fault | per-inference resource contention (`multi_bandwidth×3`) | **input / service pressure** (demand > stable service rate) |
| Action | lightweight vision profile (blocked) | **SPARSE** (interval 0.10→0.20) |
| Success | Mission latency recovery | **service continuity** under pressure |
| Must not | claim SPARSE fixes latency Mission | retune latency Mission gates so SPARSE “passes” |

Side-by-side claim template (after experiments):

```text
SPARSE is not suitable for per-inference latency recovery,
but may still be effective for capacity shedding under service pressure.
```

## Profiles (unchanged vision path)

```text
FULL:
  interval = 0.10 s
  Q_D ceiling = 1.00
  U ≈ 1.00 when healthy (Q_L=Q_S=1, valid)

SPARSE:
  interval = 0.20 s
  Q_D ceiling = 0.90
  U ≈ 0.95 when healthy
```

Same Locator + Scratch V5 (2 classifiers + detector@960). **No new vision capability.**

## Fault model: service / input pressure

**Not** primary use of `multi_bandwidth×3` (that stresses per-call GPU contention).

Target construct:

```text
λ_demand  >  λ_stable_service(profile)
```

Examples (pick one primary + document):

1. **Replay demand acceleration** — present frames / inspection opportunities faster than the profile can complete (e.g. shorter inter-arrival than `interval + inspect_time`).
2. **Synthetic inspection demand** — schedule “requested inspect” ticks at rate \(\lambda_{\mathrm{demand}}\); count completed vs requested.
3. **Camera high-rate feed** with LatestFrame — measure **stale / frame-age** when inspect cannot keep up (runtime keeps only newest frame: `gp/frames.py` — **no explicit backlog queue**).

### Runtime implication (important)

GearPro uses **LatestFrame** (drop old, keep newest). There may be **no growing queue**. Proxies for pressure accumulation:

```text
Service Deficit = max(0, λ_demand − λ_served)

or: requested inspection opportunities − completed inspections
or: frame_age_ms / stale ratio / skipped opportunities between inspects
```

Document which proxy is primary before coding the harness.

## Metrics (mechanism-matched)

| class | metrics |
| --- | --- |
| Service | inspection/service rate \(\lambda_{\mathrm{served}}\), demand–service gap, Service Deficit |
| Continuity | valid_ratio, cycle availability, drop/skip ratio |
| Freshness | frame_age_ms, stale ratio (no queue → use age/skips) |
| Quality cost | Mission Utility \(U\) (expect SPARSE ceiling ≈0.95) |
| Resources | GPU util, EMC (if available), power, temperature |
| Latency (report-only) | V5 p95 — **not** the success criterion for Secondary B |

### Capacity Mission Loss (optional aggregate)

\[
L_C = \sum_k (1 - U_k)\,\Delta t
\]

Report alongside unserved demand / Service Deficit.

## Success pattern (what “works” looks like)

```text
FULL:
  higher nominal quality (Q_D=1.00)
  but unstable service / growing deficit / frame age deteriorates

SPARSE:
  lower nominal quality (Q_D=0.90 → U≈0.95)
  but service remains bounded / valid output remains stable
```

That is capacity shedding. **Not** “SPARSE latency lower.”

## Pre-experiment: pressure characterization sweep

Find three regions before formal FULL vs SPARSE:

```text
P0 — below capacity
  FULL and SPARSE both stable

P1 — near saturation          ← most valuable
  FULL begins to degrade (deficit↑, age↑, valid↓)
  SPARSE still stable

P2 — beyond both capacities
  FULL and SPARSE both fail
```

If **P1 exists**, it is Secondary B’s operating region for the controlled comparison.

## Formal comparison (after P1 identified)

```text
same P1 service pressure
FULL vs SPARSE
report: service rate, valid ratio, frame age / deficit,
        Mission Utility, power, temperature, resource util
        (+ V5 p95 report-only)
```

Acceptance semantics (independent of latency Mission):

```text
Secondary B PASS if, under P1:
  SPARSE shows materially better service continuity
  (lower deficit / better age / higher sustained valid availability)
  at the expected quality cost (U ≈ 0.95 vs ≈ 1.00)
```

Do **not** redefine SPARSE Mission V5 latency bars to manufacture Primary A success.

## Ordered next steps

```text
1. Define service-pressure fault model + primary deficit proxy
2. Pressure-characterization sweep → locate P0 / P1 / P2
3. If P1 exists: FULL vs SPARSE controlled comparison at P1
4. Judge capacity-shedding effectiveness (not latency recovery)
5. Freeze Secondary B finding alongside Primary A / Line 1
```

## Coding gate for Secondary B harness

```text
May add: pressure generator + metrics harness (experiment branch)
Must not: change SPARSE interval / Q_D / Mission latency floors for this study
Must not: reopen CLASSIFY_ONLY or retune classifier_only_v1
```

## Decision log

| date | decision |
| --- | --- |
| 2026-09-15 | Secondary B design review opened; RQ = service continuity under input pressure; independent of Primary A |
