# Integration plan: exploration → srtp-web

Do **not** merge all of `experiment/injector-exploration` into `srtp-web` as-is.

Suggested integration branch (when ready):

```text
integration/injector-a3-measurement
base: srtp-web @ a4546e0
```

## Recommend merge (measurement infrastructure)

| path / topic | why |
| --- | --- |
| `edgemedic/gpu_pressure.py` v5 bandwidth / mem_* kinds | needed for multi-bandwidth |
| `edgemedic/multi_pressure.py` | **the** qualified injector mechanism |
| `edgemedic/injector_qual.py` | qualification gates + promote-only-on-success |
| `edgemedic/injector_report.py` | summarizer |
| `edgemedic/a3.py` `_summarize_arm` + replicas + trial checkpoints | harness correctness |
| `edgemedic/a3_capability.py` (+ report) | Case B characterization harness |
| `edgemedic/provenance.py` `llama_server=off`, frame_seq / inspect telem | provenance / rates |
| `gp/worker.py` `inspect_count` | cadence measurement |
| `gp/telemetry.py` / `gp/runtime.py` interval + count in snapshot | measurement |
| `docs/a3-strategy-capability.md` | mechanism truth + \(Q_D\) vs \(U\) |
| `docs/autonomous-session-2-status.md` | frozen Line 2 finding |
| tests for injector_qual / a3 / telemetry | keep CI green |

## Keep exploration-only (or rewrite later)

| path / topic | why |
| --- | --- |
| `edgemedic/sys_pressure.py` cpu_spin / host mem | rejected for V5 overload; thrash risk |
| `edgemedic/clock_cap.py` / `injector_clockcap_diag.py` | needs root; diagnostic only |
| `edgemedic/injector_dvfs_diag.py` | diagnostic only |
| `edgemedic/injector_explore.py` large matrices | research harness; optional |
| failed prototypes / tmp scripts | never merge |
| `results/**` | not source |

## Frozen product decision (do not “fix” in integration)

```text
Current SPARSE behavior: UNCHANGED
Mission V5 latency bars: UNCHANGED
Admission / overload gates: UNCHANGED

Next is a design choice:
  redesign latency-targeted A3 action
  OR
  open a separate capacity-shedding study for SPARSE
```

## Merge procedure (safe)

```bash
git switch srtp-web
git pull --ff-only origin srtp-web
git switch -c integration/injector-a3-measurement
# port only the files above from experiment/injector-exploration
# run unit tests + py_compile
# do NOT copy results JSON into the commit
# do NOT change SPARSE interval / mission_quality
```

## Do not change on merge

```text
admission <190
hold ≥2s
Mission V5 bars
SPARSE interval / mission_quality (strategy redesign)
```

## Research state after merge would still be

```text
Injector: QUALIFIED (multi_bandwidth ×3)
SPARSE capability: CHARACTERIZED (Case B — cadence only)
Latency-defined V5_OVERLOAD recovery via current SPARSE: NOT SUPPORTED
A3 Mission effectiveness: NOT ESTABLISHED
```
