# V2 Pressure Pilot (NX) — ENGINEERING ONLY

```text
mode: ENGINEERING ONLY
mission_approved: false
A3 effectiveness: NOT ESTABLISHED
formal quality admission: BLOCKED ON FRESH SCRATCH-ONLY HOLDOUT
previous silent run: SUSPICIOUS_ENGINEERING_EVENT (buffering vs hang UNDETERMINED)
```

Branch: `srtp-agent/v2-pressure-pilot`  
Harness: `tools/nx_v2_pressure_soak_pilot.py` (`python -u`, stage START/PASS/FAIL, hard watchdogs)

## Previous aborted run

See `v2-pressure-previous-run-event.md`. No research conclusion drawn.

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
MISSION LATENCY RECOVERY:        NOT ESTABLISHED
LATENCY RECOVERY MECHANISM:      mitigation supported; gate recovery NOT ESTABLISHED
A3 EFFECTIVENESS:                NOT ESTABLISHED
```

V2 lowers integrated Scratch latency under identical persistent pressure (~20%), but does **not** restore p95 under the Mission latency gate (190 ms).

## Engineering switch / rollback

Injector remained alive across FULL overload → V2 activation → V2 observation → FULL rollback. Rollback under pressure restored FULL topology (expected latency re-worsening is allowed and was observed in the rollback window). This supports that recovery difference tracks **profile topology**, not injector disappearance.

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

No crash, no sustained one-way latency drift, mild RSS growth consistent with allocator warmup then plateau (~2001 MiB).

## Soak

Pending / see updated JSON after 30 min V2 healthy soak completes.

## Integrated healthy baselines (planning)

```text
FULL integrated p95 ≈ 189.1 ms  (this lean healthy ≈ 179.2 ms)
V2   integrated p95 ≈ 129.5 ms  (this lean healthy ≈ 135.9 ms)
```

Early isolated probe 85.9 ms is **not** a runtime baseline.
