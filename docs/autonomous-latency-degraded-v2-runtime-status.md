# Autonomous LATENCY_DEGRADED_V2 runtime — status

```text
Agent core                         DONE
Capability registry                DONE
V2 runtime implementation          DONE
V2 topology switch                 PASS
V2 rollback                        PASS
V2 engineering soak                PASS

V2 healthy latency improvement     SUPPORTED   (~189.1 → ~129.5 ms, −31.5%)
V2 pressured latency mitigation    SUPPORTED   (397.6 → 318.4 ms, −19.9%)
V2 severe-pressure recovery        NOT SUPPORTED  (gate 190 ms not restored)

V2 quality admission               BLOCKED ON FRESH HOLDOUT
A3 Mission recovery                NOT ESTABLISHED
A3 effectiveness                   NOT ESTABLISHED

REGISTRY
  implemented=true
  mission_approved=false
  available=false
```

## Two independent blockers

Do **not** collapse these into one “only formal blocker” for Primary A / A3:

| blocker | question it blocks | status |
| --- | --- | --- |
| **Capability admission** | Can V2 pass Scratch Mission quality on a fresh holdout? | `FRESH SCRATCH-ONLY HOLDOUT` |
| **A3 Mission-recovery** | Does V2 restore p95 &lt; 190 ms under qualified severe pressure? | `V2 DOES NOT RESTORE LATENCY GATE UNDER QUALIFIED SEVERE PRESSURE` |

Even if holdout tomorrow yields `mission_approved=true`, current evidence says severe pressure remains approximately:

```text
397.6 ms → 318.4 ms
```

not:

```text
397.6 ms → <190 ms
```

So holdout success ≠ A3 Mission recovery established.

## Classification (tight)

```text
LATENCY_DEGRADED_V2
= effective LATENCY MITIGATION
≠ effective LATENCY RECOVERY capability (under qualified severe pressure)
```

Mechanism is real (workload reduction, switch, rollback, soak all PASS). Under already-qualified `multi_bandwidth ×3` persistent pressure, dropping ResNet is **not enough** to restore the Mission latency gate.

## Capability ladder (observed)

```text
SPARSE
→ does not improve per-inference latency

V2
→ per-inference latency improves (healthy −31.5%, severe −19.9%)
→ severe pressure improvement insufficient for gate recovery

future V3 (only if severity sweep shows no recovery envelope)
→ needs larger per-inspection workload reduction than “drop ResNet”
```

30 min soak PASS ⇒ current gap is **capability offload amplitude**, not runtime lifecycle instability.

## Next experiment (pre-registered)

**Do not invent V3 yet.** First map V2’s operating envelope with a fixed severity sweep:

See [v2-severity-sweep-plan.md](capability-extraction/v3/v2-severity-sweep-plan.md).

```text
S0 healthy → S1 low → S2 medium → S3 qualified severe
compare FULL vs V2: p95, ratio, gate
ask: exists reproducible FULL>190 ∧ V2<190?
```

Discipline: severities are fixed **before** looking at results. No reverse-tuning injector until V2 lands at 189 ms.

If no repeatable `FULL FAIL / V2 PASS` band:

```text
V2 = LATENCY MITIGATION CAPABILITY
V2 ≠ MISSION-RECOVERY CAPABILITY
→ then design V3 with a hard workload-reduction target
```

## Git

| item | value |
| --- | --- |
| evidence branch | `srtp-agent/v2-pressure-pilot` |
| runtime base | `integration/latency-degraded-v2-runtime` @ `b3f5cc5` |
| worktree | `G:/CODE/Machine_vision-ldv2-runtime` |
| backup (pre pressure) | `backup/pre-v2-pressure-soak-20260915-152758` |
| evidence | `docs/capability-extraction/v3/v2-pressure-pilot-nx.{json,md}` |

## Key numbers

| condition | FULL wall p95 | V2 wall p95 | reduction |
| --- | ---: | ---: | ---: |
| healthy integrated (planning) | 189.1 ms | 129.5 ms | 31.5% |
| lean healthy (this pilot) | 179.2 ms | 135.9 ms | — |
| qualified severe pressure | **397.6 ms** | **318.4 ms** | **19.9%** |

Mission latency gate: p95 &lt; 190 ms.  
Early isolated probe 85.9 ms is **not** a runtime baseline.
