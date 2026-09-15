# V2 severity sweep (NX) — ENGINEERING ONLY

```text
NOT MISSION APPROVED
NOT A3 EFFECTIVENESS
preregistered S0–S3; replicas-only knob (no post-hoc retune)
```

## Research question

Exists natural operating envelope: `FULL p95 > 190` AND `V2 p95 < 190`?

**Answer: YES — at S1 (replicas=1), both repeats.**

```text
case: A
MODERATE-PRESSURE MISSION LATENCY RECOVERY: PRELIMINARY SUPPORTED  (S1)
SEVERE-PRESSURE RECOVERY:                    NOT SUPPORTED       (S2/S3)
A3 EFFECTIVENESS:                            NOT ESTABLISHED
```

Do **not** generalize to “V2 recovers all overload”.

## Table

| Severity | replicas | repeat | FULL p95 | FULL fault | FULL gate | V2 p95 | V2 gate | V2/FULL | injector |
| --- | ---: | ---: | ---: | --- | --- | ---: | --- | ---: | --- |
| S0 | 0 | 1 | 180.4 | no | PASS | 136.3 | PASS | 0.755 | yes |
| S0 | 0 | 2 | 193.4 | no* | FAIL | 135.8 | PASS | 0.702 | yes |
| S1 | 1 | 1 | 225.8 | yes | FAIL | **178.0** | **PASS** | 0.788 | yes |
| S1 | 1 | 2 | 226.7 | yes | FAIL | **178.2** | **PASS** | 0.786 | yes |
| S2 | 2 | 1 | 319.1 | yes (characterization) | FAIL | 257.3 | FAIL | 0.806 | yes |
| S2 | 2 | 2 | 322.9 | yes (characterization) | FAIL | 257.1 | FAIL | 0.796 | yes |
| S3 | 3 | 1 | 398.7 | yes | FAIL | 322.4 | FAIL | 0.809 | yes |
| S3 | 3 | 2 | 401.1 | yes | FAIL | 324.3 | FAIL | 0.809 | yes |

\*S0 r2: FULL p95 slightly above 190 without sustained overload — thermal/noise; not a pressure fault.

S2 remains a **severity characterization point** (not auto “qualified fault” beyond latency hold criterion in this run).

## Envelope

```text
S1: FULL ~226 ms FAIL + sustained overload
    V2  ~178 ms PASS (cls2=0), injector alive
    → natural moderate recovery band
S2/S3: both FAIL gate; mitigation only (~0.80×)
```

## Plot data

- CSV: `v2-severity-sweep-nx.csv` (x=`replicas`, y=`wall_p95`; Mission gate=190)
- Script: `tools/plot_v2_severity_sweep.py` (matplotlib optional)
- JSON: `v2-severity-sweep-nx.json`

## Recommendation

```text
For proving moderate latency recovery:     V3 NOT NECESSARY
For mission-capable quality-preserving A3: V3 RECOMMENDED / LIKELY NECESSARY

Do NOT spend fresh holdout on V2.
V3 latency budget under S1: ≲10–12 ms extra vs V2 (~178 → <190).
```

See [v2-frozen-as-mechanism-demonstrator.md](v2-frozen-as-mechanism-demonstrator.md),
[v3-lightweight-fp-veto-spec.md](v3-lightweight-fp-veto-spec.md).

## Separate evidence chains

| chain | status |
| --- | --- |
| Latency mechanism (this sweep) | moderate recovery PRELIMINARY; severe NOT |
| Quality (consumed test_scratch diagnostic) | separate — see diagnostic comparison |
| Formal quality | still blocked on fresh holdout |
