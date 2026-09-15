# Previous NX pressure-soak run — suspicious engineering event

```text
classification: SUSPICIOUS_ENGINEERING_EVENT
research_conclusion: NONE DRAWN
buffering_vs_hang: UNDETERMINED
```

## Facts

| field | value |
| --- | --- |
| host | jetson-nx |
| worktree | `~/Projects/Machine_vision-ldv2-runtime` |
| HEAD (NX) | `9e08d33` (+ SCP overlay) |
| started | `2026-09-15T15:32:33+08:00` |
| aborted | `2026-09-15T16:09:02+08:00` (manual) |
| elapsed | ~36 min 24 s |
| PID | 111954 |
| flushed log | `/tmp/nx_v2_pressure_soak.log` (57 bytes) |
| RSS | ~1978992 KiB, unchanged across polls |
| CPU | ~60–69% while “silent” |
| GR3D | intermittent activity observed |

## Flushed output only

```text
HEAD=9e08d33
===START PILOT 2026-09-15T15:32:33+08:00===
```

No `[START]/`/`[PASS]` stage markers existed in that harness. Python stdout was redirected without `-u`, so **stdout buffering** and an **actual load/warmup hang** cannot be distinguished from the available evidence.

## What we do NOT conclude

- Not “proven hang”
- Not “proven buffering-only”
- No LATENCY RECOVERY MECHANISM claim
- No A3 / Mission claim

## Follow-up

Lean harness on branch `srtp-agent/v2-pressure-pilot`:

- `python -u` + `print(..., flush=True)`
- stage START/PASS/FAIL + monotonic timestamps
- hard timeouts on load / warmup / first inference / transition
- timeout diagnostics + `faulthandler` thread stacks
- soak only after lean A–F PASS
