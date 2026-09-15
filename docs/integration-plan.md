# Integration plan: exploration → measurement branch → srtp-web

Do **not** merge all of `experiment/injector-exploration` or
`experiment/secondary-b-capacity` wholesale into `srtp-web`.

Active measurement branch:

```text
integration/injector-a3-measurement
```

A3 strategy study is **closed** for current actions — see
[a3-strategy-matrix.md](a3-strategy-matrix.md). Promote infrastructure; do not
reopen Agent A3 invention.

## Already on integration (baseline)

Qualified injector + Case B / A3 measurement stack through `6e28fff` and earlier:

| path / topic | why |
| --- | --- |
| `edgemedic/gpu_pressure.py`, `multi_pressure.py` | qualified injector |
| `edgemedic/injector_qual.py`, `injector_report.py` | qualification |
| `edgemedic/a3.py`, `a3_capability.py` | A3 / Case B harness |
| `edgemedic/provenance.py` | provenance |
| related `gp/` telemetry / worker inspect counts | measurement |
| tests for injector / a3 | CI |

## Promote next (from `experiment/secondary-b-capacity`, cleanly)

| path / topic | why | note |
| --- | --- | --- |
| `gp/types.py` / `gp/worker.py` / `gp/runtime.py` freshness fields | InspectionAge / FrameLag | non-invasive measurement |
| `edgemedic/secondary_b_metrics.py` | intentional_skip vs pressure_miss | keep |
| `edgemedic/secondary_b_feasibility.py` | feasibility harness | keep; pilot-only |
| `tests/test_secondary_b_metrics.py` | unit coverage | keep |
| `docs/a3-strategy-matrix.md` | closed strategy matrix | **canonical status** |
| `docs/autonomous-secondary-b-status.md` | Secondary B mechanism否证 | keep |
| `docs/secondary-b-capacity-shedding-design.md` | design record | keep |
| `docs/secondary-b-feasibility-pilot-SUMMARY.md` (+ json summary) | pilot summary | keep; not raw NX dumps |
| `docs/edgemedic.md` status compression | hub status | keep |
| `docs/capability-extraction/**` markdown + frozen JSON configs | Primary A record | **exclude** `dataset_defects/` images/xml |
| Primary A harness scripts (`latency_probe_*`, `locked_test_*`, `freeze_*`) | reproducibility of rejected capability | optional; mark historical |

Preferred promote method:

```text
1. cherry-pick f083f09 (freshness + Secondary B harness only)
2. add docs / capability-extraction text+JSON without dataset_defects
3. do NOT cherry-pick b4ad9df wholesale (accidental val image dump)
```

## Keep exploration-only

| path / topic | why |
| --- | --- |
| `docs/capability-extraction/dataset_defects/**` | accidental bulk; training data not for GearPro merge |
| `edgemedic/sys_pressure.py`, clock_cap / dvfs diags | rejected / needs root |
| `edgemedic/injector_explore.py` large matrices | research optional |
| `results/**`, `results_secondary_b_*` local copies | not source |
| `tmp_*.sh`, `backup/**` | never merge |
| failed prototypes that change runtime service semantics (queues, etc.) | diagnostic only |

## Frozen product decisions (do not “fix” in integration)

```text
Current SPARSE interval / Q_D: UNCHANGED
Mission V5 latency bars / utility floors: UNCHANGED
Admission / overload gates: UNCHANGED

SPARSE latency recovery: NOT SUPPORTED
SPARSE capacity shedding: NOT SUPPORTED
classifier_only_v1: RUNTIME REJECTED — do not open CLASSIFY_ONLY on it
Primary A: BLOCKED ON VISION CAPABILITY
A3 effectiveness: NOT ESTABLISHED
No new Agent A3 actions until a new lightweight capability passes Mission contract
```

## Merge procedure (safe)

```bash
git switch integration/injector-a3-measurement
git pull --ff-only origin integration/injector-a3-measurement
# cherry-pick f083f09 OR port listed paths from experiment/secondary-b-capacity
# add strategy-matrix + status docs + capability-extraction text/JSON only
# run unit tests + py_compile
# do NOT copy results JSON trees or dataset_defects into the commit
# do NOT change SPARSE interval / mission_quality / Mission bars
```

When later promoting to `srtp-web`: review PR; exclude research-only harnesses if product tree should stay lean; never merge exploration bulk.

## Research state after promote (unchanged claims)

```text
Line 1 — COMPLETE / REPRODUCED
Restart baseline      CHARACTERIZED
SPARSE latency        NOT SUPPORTED
SPARSE capacity       NOT SUPPORTED
classifier_only_v1    RUNTIME REJECTED BY MISSION CONTRACT
Primary A             BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY
A3 effectiveness      NOT ESTABLISHED
```
