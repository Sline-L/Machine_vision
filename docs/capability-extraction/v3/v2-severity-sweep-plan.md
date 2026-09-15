# V2 pressure severity sweep — pre-registered plan

```text
mode: ENGINEERING ONLY
purpose: map LATENCY_DEGRADED_V2 recovery operating envelope
NOT: reverse-tune injector until V2 passes gate
NOT: A3 effectiveness claim
NOT: quality admission
```

## Research question

Is there a **natural, pre-defined** severity band where:

```text
FULL wall p95  ≥ 190 ms   (Mission latency gate FAIL)
V2   wall p95  < 190 ms   (gate PASS)
```

with repeatable FULL overload under that same severity?

If yes → V2 = recovery for **moderate** overload; mitigation-only under **severe**.  
If no  → V2 = **LATENCY MITIGATION CAPABILITY** only; then consider V3.

## Discipline (frozen)

1. Severity levels are defined **before** measurement.
2. Report the full response curve; do not drop “inconvenient” levels.
3. **Forbidden:** adjust injector after seeing results so V2 lands near 189 ms.
4. Same crops / replay pack / measurement window / cool-down rules for every cell.
5. Injector must stay alive for both FULL and V2 arms at each severity.
6. Do not change weights, threshold, fusion, imgsz, Mission gate, or Q_D.

## Pre-defined severities

Family: `multi_bandwidth` replicas (same kind as qualified severe).  
Vary **replicas** only for this sweep so severity is one ordered knob.  
Other fields locked to the qualified config:

```text
kind      = bandwidth
bytes_mb  = 512
buffers   = 3
streams   = 4
load_ms   = 100
idle_ms   = 0
```

| id | label | replicas | intent |
| --- | --- | ---: | --- |
| **S0** | healthy | 0 (injector off) | no added contention |
| **S1** | low | 1 | light contention |
| **S2** | medium | 2 | intermediate |
| **S3** | qualified severe | 3 | already-qualified severe (known FULL≈398 / V2≈318) |

S3 is the **anchor** already measured; re-run once in this sweep for same-session comparability, do not retune it.

## Per-cell protocol

For each Si:

```text
1. cool / confirm healthy startup
2. start injector at Si (noop for S0)
3. settle briefly
4. FULL bringup → observation window → record
5. V2 bringup (same injector still ON) → observation window → record
6. stop injector
7. cool before next severity
```

Alternate FULL/V2 order across repeats if time allows; otherwise record order + thermal state.

Suggested window: 40–50 s observation after settle (match lean pilot).  
Repeats: ≥2 paired runs per severity when feasible; S0 may be single if matches known healthy baseline.

## Metrics (every cell)

```text
severity_id
injector config + hash + alive
FULL wall p50/p95/max
V2   wall p50/p95/max
V2/FULL p95 ratio
FULL gate190 (p95 < 190)
V2   gate190
FULL sustained_overload (≥200 ms hold ≥2 s) — latency-based only
V2 cls2_p95 (must be 0)
valid_ratio, inspect rate
temp / GPU util / GPU clock / RSS
```

## Envelope decision rule (pre-registered)

After the full curve:

```text
RECOVERY_ENVELOPE_FOUND
  iff ∃ Si with ≥2 consistent repeats where:
    FULL gate190 = false
    V2   gate190 = true
    injector alive throughout
    V2 cls2_p95 = 0

else:
  V2 = LATENCY MITIGATION CAPABILITY
  V2 ≠ MISSION-RECOVERY CAPABILITY
  → V3 design may start with explicit workload-reduction target
```

Do **not** interpolate a fake “189 ms sweet spot” between discrete Si values and call it established recovery.

## Outputs

```text
docs/capability-extraction/v3/v2-severity-sweep-nx.json
docs/capability-extraction/v3/v2-severity-sweep-nx.md
```

Table required:

| severity | FULL p95 | V2 p95 | ratio | FULL gate | V2 gate | injector alive |

Plus narrative: envelope found / not found; still **A3 effectiveness = NOT ESTABLISHED**.

## What this does not unlock

- `mission_approved=true`
- production Reflex `V5_OVERLOAD → LATENCY_DEGRADED_V2`
- claim that holdout alone finishes Primary A
