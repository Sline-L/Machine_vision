# V2 Pressure Pilot (NX) — ENGINEERING ONLY

```text
mode: ENGINEERING ONLY
mission_approved: false
A3 effectiveness: NOT ESTABLISHED

Capability admission blocker:  FRESH SCRATCH-ONLY HOLDOUT
A3 Mission-recovery blocker:   V2 DOES NOT RESTORE LATENCY GATE
                               UNDER QUALIFIED SEVERE PRESSURE
```

Branch: `srtp-agent/v2-pressure-pilot`  
Harness: `tools/nx_v2_pressure_soak_pilot.py` (`python -u`, stage START/PASS/FAIL, hard watchdogs)

## Headline correction

```text
LATENCY_DEGRADED_V2
= effective latency MITIGATION
≠ effective latency RECOVERY under qualified severe pressure
```

| condition | FULL p95 | V2 p95 | reduction |
| --- | ---: | ---: | ---: |
| healthy (planning integrated) | ≈189.1 ms | ≈129.5 ms | **31.5%** |
| qualified severe (`×3`) | **397.6 ms** | **318.4 ms** | **19.9%** |

Mechanism is real; ResNet removal is **not enough** to cross the 190 ms Mission gate under already-qualified severe pressure. Fresh holdout success would still leave this A3 recovery gap.

## Previous aborted run

See `v2-pressure-previous-run-event.md`. Buffering vs hang **UNDETERMINED**. No research conclusion.

## Lean A–F (PASS)

| stage | result |
| --- | --- |
| A FULL healthy | PASS — wall p95 **179.2 ms**, gate190 true |
| B V2 healthy | PASS — wall p95 **135.9 ms**, cls2 p95 **0**, gate190 true |
| C FULL + qualified pressure | PASS — wall p95 **397.6 ms**, gate190 **false**, sustained_overload **true**, injector alive |
| D V2 + same pressure | PASS — wall p95 **318.4 ms**, gate190 **false**, cls2 **0**, injector alive |
| E engineering FULL→V2 under pressure | PASS |
| F rollback FULL under pressure | PASS — injector still alive through rollback |

Qualified injector (unchanged for both arms):

```text
multi_bandwidth × 3
bytes_mb=512 buffers=3 streams=4 load_ms=100 idle_ms=0
hash=49da7bb852cb5e733fc505eb3bfe5c89f7992c8e8427840bc4e9d3c3ffbfd70f
```

### Paired delta (lean)

| metric | FULL pressure | V2 pressure |
| --- | ---: | ---: |
| wall p95 | 397.6 ms | 318.4 ms |
| gate p95 &lt; 190 | FAIL | FAIL |
| ratio V2/FULL | — | **0.801** |
| Δp95 (V2−FULL) | — | **−79.2 ms** |

### Classification (latency only)

```text
LATENCY MITIGATION:              SUPPORTED
MISSION LATENCY RECOVERY:        NOT ESTABLISHED / NOT SUPPORTED @ S3
A3 EFFECTIVENESS:                NOT ESTABLISHED
```

## Engineering switch / rollback

Injector remained alive across FULL overload → V2 → rollback FULL. Difference tracks **profile topology**, not injector disappearance.

## Soak

```text
ENGINEERING SOAK: PASS
duration: ~1800 s (109 × ~15 s windows)
global wall p50: 127.0 ms
global wall p95: 136.6 ms
last-10-min wall p95 mean: 137.5 ms
rss growth: +117.4 MiB (< 250 MiB threshold)
exceptions: 0
profile identity: stable (cls2=0 throughout)
crash: none
```

Lifecycle is stable; the remaining gap is **offload amplitude**, not soak fragility.

## Next

Pre-registered severity sweep (S0–S3), not V3 yet:  
[v2-severity-sweep-plan.md](v2-severity-sweep-plan.md)

## Integrated healthy baselines (planning)

```text
FULL integrated p95 ≈ 189.1 ms  (this lean healthy ≈ 179.2 ms)
V2   integrated p95 ≈ 129.5 ms  (this lean healthy ≈ 135.9 ms)
```

Early isolated probe 85.9 ms is **not** a runtime baseline.
