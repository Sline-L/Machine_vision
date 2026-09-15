# V3-1 gate completion — freeze + NX S1

```text
exploration_commit: 2377521
fresh_holdout: UNTOUCHED
registry: UNCHANGED
V3-2 / V3-3: NOT STARTED
train/val retune: STOPPED
```

## Gate 1 — Engineering Freeze

Package: `docs/capability-extraction/v3/v3-1-engineering-freeze/`

- `v3-1-engineering-freeze.json` / `.md`
- split manifests + hashes
- param lock: no V3-1 changes before holdout adjudication

## Gate 2 — NX S1 paired latency

| arm | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| V2 mean | 170.69 | **175.94** | 177.65 |
| V3-1 mean | 172.47 | **177.93** | 179.11 |
| **delta_p95** | — | **+1.99 ms** | — |

```text
V3-1 p95 < 190: PASS
delta_p95 ≤ 12 ms: PASS
injector alive: PASS

RESULT: PASS
STATUS: V3-1 ENGINEERING-QUALIFIED CANDIDATE
NOT: validated / production-ready / mission_approved
```

Microbench (~0.005 ms) underestimated plumbing (~2 ms integrated delta) but still well inside budget.

## Holdout

Preregistration committed: `v3-1-fresh-holdout-preregistration.md`  
**Do not open holdout** until human adjudication gate.
