# Autonomous session 2 status — SPARSE capability characterization

## 1. Code state

```text
stable:      srtp-web @ a4546e0
backup:      backup/pre-autonomous-exploration-20260914 @ a4546e0
exploration: experiment/injector-exploration @ ca790c5 (pushed)
user a3 patch: backup/pre-autonomous-a3.py.patch (preserved)
```

New commits this session (on exploration branch):

```text
43cd50a feat(edgemedic): add SPARSE capability analysis and severity response harness
288f1c5 fix(edgemedic): improve capability rate metric and add check grid
ca790c5 fix(runtime): expose inspection_count and interval for cadence measurement
```

NX note: GitHub DNS failed mid-session; telemetry/capability files were SCP’d for the rate_check_v2 run. Formal provenance for that run is SCP-dirty relative to clean ff-only; latency response table v1 was on clean `43cd50a`.

## 2. What SPARSE actually does

Source: `gp/profiles.py`, `gp/worker.py`, `docs/a3-strategy-capability.md`.

```text
FULL:
  interval = 0.10 s
  Locator + V5 classifiers + P2 detector every inspect
  mission_quality ceiling = 1.00

SPARSE:
  interval = 0.20 s   ← only runtime workload change
  same Locator + same V5 path (detector still on, imgsz 960)
  mission_quality ceiling = 0.90
```

```text
Difference:
  cadence / wait between inspects
  Mission Utility ceiling

Unchanged:
  per-call Scratch V5 compute
  detector / classifiers
  locator backend (keep)
```

Therefore single-inference V5 latency is **not** expected to drop under SPARSE by design.

Mission Verify for SPARSE still requires `v5_p95 ≤ 220 ms` (`gp/verify.py`) — a **latency** bar on a **rate** degradation.

## 3. Severity response table

Injector fixed: `multi_bandwidth ×3`, `bytes_mb=512`, duty = load/idle.

### Primary sweep (`results/a3_capability/severity_response_v1`)

Cycle rates in this file are **invalid** (snapshot last-result artifact). Use V5/locator/utility only:

| severity | load/idle | profile | V5 p50 | V5 p95 | locator p95 | utility |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| S0 | OFF | FULL | 165.8 | 184.5 | 65.9 | 1.00 |
| S0 | OFF | SPARSE | 148.6 | 181.6 | 66.1 | 0.95 |
| S1 | 40/60 | FULL | 169.0 | 225.3 | 90.1 | 1.00 |
| S1 | 40/60 | SPARSE | 167.8 | 217.8 | 87.8 | 0.95 |
| S2 | 60/40 | FULL | 187.6 | 235.2 | 92.8 | 1.00 |
| S2 | 60/40 | SPARSE | 203.7 | 243.6 | 92.4 | 0.95 |
| S3 | 75/25 | FULL | 223.9 | 260.2 | 91.6 | 1.00 |
| S3 | 75/25 | SPARSE | 214.2 | 254.9 | 90.9 | 0.95 |
| S4 | 90/10 | FULL | 252.8 | 304.8 | 93.2 | 1.00 |
| S4 | 90/10 | SPARSE | 251.1 | 309.5 | 95.3 | 0.95 |
| S5 | 100/0 | FULL | 276.7 | 323.7 | 94.1 | 1.00 |
| S5 | 100/0 | SPARSE | 278.3 | 319.2 | 94.9 | 0.95 |

valid_ratio = 1.0 everywhere. GPU clock → 1173 MHz whenever injector ON.

### Rate-corrected check (`results/a3_capability/rate_check_v2`)

After `inspection_count` telemetry:

| severity | profile | V5 p95 | **inspect rate Hz** | utility | interval_s |
| --- | --- | ---: | ---: | ---: | ---: |
| S0 | FULL | 180.2 | **3.21** | 1.00 | 0.10 |
| S0 | SPARSE | 181.8 | **2.46** | 0.95 | 0.20 |
| S1 | FULL | 218.9 | **3.06** | 1.00 | 0.10 |
| S1 | SPARSE | 221.4 | **2.36** | 0.95 | 0.20 |
| S5 | FULL | 324.5 | **2.36** | 1.00 | 0.10 |
| S5 | SPARSE | 327.9 | **1.90** | 0.95 | 0.20 |

Consistent with `cycle ≈ V5_latency + interval` (not pure interval).

## 4. Curves / result paths

```text
docs/a3-strategy-capability.md
docs/integration-plan.md
results/a3_capability/severity_response_v1/summary.json
results/a3_capability/severity_response_v1/response_table.csv
results/a3_capability/rate_check_v2/summary.json
results/a3_capability/rate_check_v2/response_table.csv
```

## 5. Mechanism conclusion

**Case B** (frozen)

> Under sustained memory-bandwidth pressure, the current SPARSE profile
> reduces inspection cadence but leaves the per-inference V5 computation
> path unchanged. Consequently, it lowers service rate without materially
> reducing V5 inference latency, and therefore does not restore a
> latency-gated Mission under persistent overload.

Clarification: profile `mission_quality` \(Q_D\) is 0.90 on SPARSE; aggregate
Mission Utility \(U=0.3Q_L+0.5Q_D+0.2Q_S\) reports **≈0.95** when \(Q_L=Q_S=1\).
Tables showing utility 1.00→0.95 refer to \(U\), not \(Q_D\).

**A3 strategy suitability for latency-defined V5_OVERLOAD:** NOT SUPPORTED by current SPARSE.

**Route lock:** Primary **A** reframed (dataset already has classifier-only; extraction in `docs/capability-extraction/`). Blocked on freeze + Mission utility — not on inventing a new vision stack. `CLASSIFY_ONLY` not opened; Mission thresholds unchanged.

## 6. Bug / measurement fixes

| item | commit | effect |
| --- | --- | --- |
| `inspection_count` + `inference_interval_s` in snapshot | `ca790c5` | enables true cadence measurement |
| capability harness uses count delta for `cycle_rate_hz` | same | rate_check_v2 valid |
| severity response harness | `43cd50a` | FULL/SPARSE steady-state grid |

Not strategy redesign. No Mission threshold changes.

## 7. A3 implication

> Is current SPARSE worth continuing as the V5_OVERLOAD A3 recovery strategy?

**limited / not supported for latency-based Mission recovery**

Reason: under persistent bandwidth contention, Mission fails on **per-inference V5 p95**, while SPARSE only reduces **invocation rate**. FUNCTION verify can still succeed; MISSION does not while pressure remains.

Next product/research decision (for user, not this session): redesign degradation action and/or Mission criterion for this fault class — do **not** retune 220 ms to chase SPARSE.

## 8. Integration recommendation

See `docs/integration-plan.md`.

Recommend later cherry-pick into `integration/injector-a3-measurement`:

- multi_pressure + bandwidth injector
- injector_qual / a3 harness fixes
- a3_capability + strategy docs
- inspection_count telemetry

Keep exploration-only: sys_pressure cpu_spin, clock-cap, DVFS diag, failed explore matrices.

Do **not** bulk-merge exploration → `srtp-web` yet.

## 9. Final research state

```text
Injector: QUALIFIED (multi_bandwidth ×3)

SPARSE capability: CHARACTERIZED
  → Case B: rate/capacity degradation only
  → no material per-inference V5 mitigation under bandwidth pressure

A3 severe-pressure pilot:
  MISSION 0/3 vs 0/3 (prior session)

A3 strategy suitability: LIMITED / NOT SUPPORTED
  for latency-defined V5_OVERLOAD Mission recovery

A3 effectiveness: NOT YET ESTABLISHED
```
