# Mission contract — `classifier_only_v1`

Layer: **Mission / quality policy** (separate from objective capability facts).  
Capability facts: [classifier_only_v1.capability.json](classifier_only_v1.capability.json).

```text
quality_policy.Q_D_rule:  min(Recall, 1 - FPR)   PREREGISTERED
quality_policy.Q_D,val:   0.9065420560747663
mission_acceptance.minimum_utility: 0.85
mission_acceptance.accepted: true
mission_semantics_acceptance: PASS
```

## Mission semantics acceptance: PASS

> **`classifier_only_v1` preserves the mission-required binary Scratch defect verdict (`GOOD/DEFECT` / 合格/不合格) while intentionally dropping auxiliary Scratch localization (`auxiliary_box`). Scratch localization is treated as a non-mission-critical auxiliary capability under the current GearPro mission contract.**

Two layers (must keep both):

```text
Mission-critical:
Scratch presence / binary defect verdict       PRESERVED

Auxiliary capability:
Scratch bbox / visual localization             DEGRADED
```

classifier-only is **not** capability-equivalent to FULL; it loses detector local Scratch boxes. Under the **current code-defined Mission**, that does not break the required task output.

### Code evidence (`srtp-web` / GearPro)

| claim | evidence |
| --- | --- |
| Defect = score vs threshold | `InspectionResult.is_defective` — observations with `defect_score >= defect_threshold`; `verdict` is 合格/不合格 only (`gp/types.py`) |
| Serial is binary | `serial.send_verdict(result.is_defective)` (`gp/runtime.py`, `gp/serial_io.py`) |
| `auxiliary_box` is auxiliary | Mapped/drawn in `TwoStageInspector._draw_observation`; not used in verdict |
| Mission Verify has no bbox gate | Window cycles, valid ratio, Locator/V5/elapsed p95, utility, health/incidents (`gp/verify.py`) — no localization completeness |

**Locked-test note (preregistered):** bbox loss is **known and accepted**; it is **not** a locked-test acceptance criterion. Locked test validates only the frozen **binary defect** capability (Recall/FPR → same \(Q_D\) rule), plus that the frozen threshold is not retuned.

---

## What `Q_D` is (and is not)

Detection Quality \(Q_D\) is a **normalized mission-level quality coefficient** from the preregistered rule below — **not** equated to recall, precision, F1, or any single model metric.

\[
U = 0.3\,Q_L + 0.5\,Q_D + 0.2\,Q_S
\]

Runtime: `Q_D_runtime = valid_output_ratio × profile.mission_quality`.  
When CLASSIFY_ONLY is opened, `mission_quality` shall be the assigned \(Q_D\) from this contract (val now; locked-test \(Q_D\) for reporting under the same rule).

Placeholder `mission_quality: 0.65` for unimplemented `CLASSIFY_ONLY` must **not** be reused.

---

## Preregistered \(Q_D\) rule (LOCKED)

```text
Q_D = min(Recall, Specificity)
    = min(Recall, 1 - FPR)

Rationale:
Weakest of (1) retaining defectives and (2) preserving normals.
Fixed before locked-test evaluation.
No post-test reweighting.
```

Rejected: \(Q_D=\)Recall / F1 / Balanced Accuracy / ad-hoc tiers / 7:3 cost weights without production evidence / FULL-relative interpolation.

### Validation application

```text
Recall = 0.9534883720930233
FPR    = 0.09345794392523364
Q_D,val = min(0.9534883720930233, 0.9065420560747663) = 0.9065420560747663
U_val   = 0.5 + 0.5 × Q_D,val = 0.9532710280373832   (Q_L=Q_S=1)
```

Admission \(Q_D \ge 0.70\) for \(U \ge 0.85\): **PASS**.

---

## Contract freeze fields (for runtime later)

```text
profile_id:              classifier_only_v1
mission_quality (Q_D):   0.9065420560747663   # from val under locked rule; locked-test recomputes report-only
threshold:               0.5986470981744116
fusion:                  classifier_mean
detector_enabled:        false
minimum_mission_utility: 0.85
semantics:               binary scratch verdict required; bbox auxiliary / non-criteria
```

---

## Status

| item | status |
| --- | --- |
| Objective capability frozen | PASS |
| Latency benefit | PASS |
| Provenance | PASS |
| \(Q_D\) rule | PASS |
| \(Q_D,\mathrm{val} \ge 0.70\) | PASS |
| Mission semantics | **PASS** |
| `mission_acceptance.accepted` | **true** |
| Capability contract | **READY TO FREEZE / FROZEN at Step 3 close** |
| `CLASSIFY_ONLY` implementation | **NOT STARTED** (next only after locked-test PASS) |
