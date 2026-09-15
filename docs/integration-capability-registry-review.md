# Integration review — fail-closed capability registry

Subject: selective promote from `experiment/lightweight-capability-v2` @ `e36679b`  
Into: `srtp-web`  
Date: 2026-09-15

**Verdict: PASS — promote infrastructure only**

## Absorb

| path | why |
| --- | --- |
| `gp/capability_registry.py` | fail-closed admission |
| `docs/capabilities/registry.json` | declarative statuses |
| `gp/profiles.py` | gate `apply_to_config` |
| `gp/runtime.py` | `state()["capabilities"]` read-only |
| `tests/test_capability_registry.py` | reject unapproved / REJECTED |
| `docs/capability-extraction/v2/admission-state-machine.md` | state machine provenance |

## Do **not** absorb (remain on experiment)

```text
docs/capability-extraction/v2/candidate-inventory.md
docs/capability-extraction/v2/data-split-provenance.md
docs/capability-extraction/v2/latency-pareto.md
docs/capability-extraction/v2/classifier-v1-failure-analysis.md
docs/autonomous-lightweight-capability-status.md
```

Those are exploration / negative-result packaging, not runtime.

## Safety checks

| check | result |
| --- | --- |
| FULL / SPARSE still switchable | yes |
| CLASSIFY_ONLY still unimplemented | yes |
| `classifier_only_v1` REJECTED → unavailable | yes |
| spoofed `mission_approved` on REJECTED | denied |
| `gp/scratch_v5.py` unchanged | yes |
| SPARSE / Mission gates / Q0–Q3 unchanged | yes |

## Semantics

```text
Vision artifact
  → Capability contract
  → Registry
  → implemented AND mission_approved
  → YES: Control/Guardian may switch
  → NO: runtime unavailable
```

Rejected ids are terminal. Existence in registry ≠ availability.
