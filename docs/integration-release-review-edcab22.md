# Integration release review — `edcab22` → `srtp-web`

Review date: 2026-09-15  
Subject: `integration/injector-a3-measurement` @ `edcab22`  
Base for delta: `a4546e0` (= current `origin/srtp-web` tip / merge-base)  
Purpose: decide whether this measurement-complete branch is safe to merge into `srtp-web`.

**Reviewer verdict: PASS — recommend merge + tag**

```text
edgemedic-a2a3-measurement-baseline
```

Meaning of the tag (if applied after merge):

> A2/containment has reproducible evidence; A3 measurement framework is complete;
> current A3 candidate strategies are mechanistically characterized;
> **A3 effectiveness is not established.**

Do **not** interpret merge as opening new A3 actions or claiming effectiveness.

---

## Check 1 — Diff scope (`a4546e0..edcab22`)

**PASS.** 4 commits, 55 paths, +6353 / −51. Contents are measurement / telemetry / harness / provenance / docs only.

| Bucket | Paths (representative) |
| --- | --- |
| Injector / qual | `edgemedic/gpu_pressure.py` v5, `multi_pressure.py`, `injector_qual.py`, `injector_report.py` |
| A3 / Case B harness | `edgemedic/a3.py` summarize+replicas, `a3_capability.py`, `a3_capability_report.py` |
| Freshness / cadence telem | `gp/types.py`, `gp/worker.py`, `gp/runtime.py`, `gp/telemetry.py`, `edgemedic/provenance.py` |
| Secondary B harness | `secondary_b_*.py`, `tests/test_secondary_b_metrics.py` |
| Primary A record (rejected) | `docs/capability-extraction/**` (no `dataset_defects/`), freeze/locked/latency probe scripts |
| Strategy closure docs | `a3-strategy-matrix.md`, status docs, `integration-plan.md`, `edgemedic.md` |

**Not in the delta (good):**

```text
gp/profiles.py  gp/verify.py  gp/guardian.py  gp/actions.py  gp/control.py
gp/scratch_v5.py  gp/models.py  gp/weights.py  gp/bundle.py
edgemedic/reasoner.py  edgemedic/policy.py  edgemedic/memory.py
```

No vision weights, no queue redesign, no new Agent tools.

Soft note (acceptable for measurement baseline): research harness scripts
(`freeze_classifier_mean_val.py`, `locked_test_*`, `latency_probe_*`,
`secondary_b_feasibility.py`) ship with the branch. They do not change runtime
defaults; they document a closed study.

---

## Check 2 — Frozen product / research knobs

**PASS.** Explicit zero-diff on strategy-critical modules; spot-check values unchanged:

| Knob | Status |
| --- | --- |
| SPARSE interval 0.10→0.20 / \(Q_D\) 0.90 | unchanged (`gp/profiles.py` not in delta) |
| Mission V5 bars / utility floors | unchanged (`gp/verify.py` not in delta; tests still assert SPARSE 220 ms / U) |
| Vision model / fusion / thresholds | unchanged |
| Guardian / Reflex / whitelist tools | unchanged (`policy` / `reasoner` / `guardian` not in delta) |
| Q0–Q3 experiment definitions | not rewritten; docs only update research status |
| `CLASSIFY_ONLY` | still `implemented: False` |

`gp/worker.py` adds timestamps + `inspect_count` and one extra `frame_store.read()` after inspect for FrameLag. Scheduling remains LatestFrame + `wait(inference_interval)`; inspect path unchanged.

---

## Check 3 — Tests

Environment: local `.venv` on Windows review host.

```text
python -m py_compile  (AGENTS.md gp/* + edgemedic measurement modules)  OK
python -m unittest discover -s tests -v
  Ran 125 tests
  FAILED (failures=1, errors=1)  — same two on a4546e0 baseline
```

| Result | Test | Cause | Regression? |
| --- | --- | --- | --- |
| FAIL | `test_config_resolves_relative_weights_and_checks_hashes` | Windows 8.3 vs long path equality | **No** — identical on `a4546e0` |
| ERROR | `test_real_model_bundle_loads_on_cpu` | `torch` not installed in this venv | **No** — identical on `a4546e0` |

Relevant suites all green, including:

```text
test_profiles (SPARSE interval / utility)
test_verify (SPARSE mission window)
test_edgemedic_policy / test_actions / test_edgemedic_a3
test_edgemedic_injector_qual (admission 190)
test_edgemedic_memory (whitelist / CLASSIFY_ONLY reject)
test_secondary_b_metrics (new)
test_web / control auth (when deps present)
```

`npm run build` not re-run: no `web/` changes in this delta.

NX hardware replay not required for this software merge gate.

---

## Check 4 — Local untracked hygiene

**PASS after ignore rules** (backups not deleted).

Previously visible untracked:

```text
backup/
results_secondary_b_feasibility_pilot_1/
tmp_launch_stage_c.sh
tmp_repro_q.sh
tmp_stage_c_controlled.sh
```

`.gitignore` now includes:

```text
backup/
tmp_*.sh
results_secondary_b_*/
docs/capability-extraction/dataset_defects/
```

`backup/` remains on disk for recovery; it must not be committed or force-cleaned.

---

## Post-merge waiting state (recommended status line)

```text
Agent/runtime architecture        COMPLETE
Line 1 evidence                   COMPLETE
A3 measurement infrastructure     COMPLETE
Current A3 strategies             CHARACTERIZED
Acceptable lightweight capability MISSING
Production-line validation        FUTURE

A3 effectiveness                  NOT ESTABLISHED
```

Next SRTP work classes (not “more Agent features”):

1. Results / RQ / figures / thesis narrative  
2. Wait for new lightweight vision capability → reopen Primary A via  
   `freeze → contract → runtime profile → Guardian → Verify → pressure experiment`

---

## Merge recipe (when user approves)

```bash
git switch srtp-web
git pull --ff-only origin srtp-web
git merge --ff-only origin/integration/injector-a3-measurement   # expects FF a4546e0..edcab22
git push origin srtp-web
git tag -a edgemedic-a2a3-measurement-baseline -m "A2 evidence + A3 measurement complete; strategies characterized; effectiveness NOT ESTABLISHED"
git push origin edgemedic-a2a3-measurement-baseline
```

Do **not** force-push. Do **not** merge exploration branches (`experiment/secondary-b-capacity` bulk / `dataset_defects`) into `srtp-web`.
