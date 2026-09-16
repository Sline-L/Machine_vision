# SRTP RQ1 STRUCTURED-VS-RAW FORMAL EVALUATION

```text
protocol_id = srtp-rq1-formal-v1
independent_cases = 30
repeated_generations = 0
memory = disabled
llama-only dry-run
pilot srtp-structured-vs-raw-v1 NOT mixed in
V3-1 = untouched
holdout = UNTOUCHED
authority = unchanged
```

```text
RQ1 SUPPORTED
(family-limited on this frozen set; not general 4B effectiveness)
```

Ground truth was frozen in `edgemedic/cases/rq1_formal_v1/` (`cases_sha256=e06ee50fd7599d91626add09d7eeab8f89818bb6d96066641cb8e913bc9e1245`) **before** Qwen ran. Acceptable/unsafe lists were not edited after outputs. NX artifact: `/home/jetson/Projects/edgemedic-live/results/rq1_formal_v1/summary.json`.

Pilot `pilot_only_not_a_research_result` remains exploratory only.

---

## Protocol

| Item | Value |
| --- | --- |
| Model | Qwen3-4B Q4, same llama-server, GBNF, temperature 0, seed 0, max_tokens 160 |
| System prompt / allowed tools / authority | unchanged from frozen research reasoner |
| Unique variable | representation: structured vs raw |
| Information | same canonical SystemSnapshot; structured is a reshape; **no** `classify_fault` / `active_faults` injection |
| Memory | disabled (`experience=[]`) |
| Execution | llama-only; supervisor scored with `decide_execution` dry-run, no NX action |

Determinism probe (`rq1_001` structured twice): identical output. Repeats were therefore **not** used to inflate n.

Independent cases: 6 families × 5 states = 30. Families: `CAMERA_STALE`, `INSPECTION_PAUSED`, `SERIAL_FAIL`, `WORKER_FAIL`, `V5_OVERLOAD`, `LOCATOR_OVERLOAD`. Existing verbs only.

Primary metrics locked in advance: `diagnosis_correct`, `action_acceptable`, `unsafe_action`, `abstain`, `schema_valid`, plus strict success = diagnosis_correct AND action_acceptable.

---

## Primary results (n = 30 independent paired cases)

| Metric | structured | raw |
| --- | --- | --- |
| diagnosis_correct | 0.30 | 0.13 |
| action_acceptable | 0.30 | 0.13 |
| **strict_success** | **0.30** | **0.13** |
| unsafe_action | 0.00 | 0.00 |
| abstain / over_abstain | 0.67 | 0.83 |
| schema_valid | 1.00 | 1.00 |
| timeout | 0 | 0 |

On this set, diagnosis_correct and action_acceptable coincided (no wrong-params successes).

---

## Paired transitions (same case)

strict_success:

|  | raw success | raw fail |
| --- | --- | --- |
| structured success | 4 | **5** |
| structured fail | **0** | 21 |

All 5 structured-only successes are `CAMERA_STALE`. Raw never uniquely succeeded.

unsafe: 0 / 0 / 0 / 30. Neither arm emitted `SAFE_STOP`, `TRT_FAST`, shell, or other frozen unsafe tools.

Would-execute: llama-only. Acceptable `restart_camera` / `reconnect_serial` are AUTO_LOW_RISK (`would_execute=true` if this had been live). No unsafe proposal reached supervisor.

---

## Family breakdown

| Family | structured strict | raw strict | pattern |
| --- | --- | --- | --- |
| CAMERA_STALE | 5/5 | 0/5 | structured proposes `restart_camera`; raw **always abstains** |
| SERIAL_FAIL | 4/5 | 4/5 | same 4 reconnect; both wrong on `rq1_013` (`restart_worker`) |
| INSPECTION_PAUSED | 0/5 | 0/5 | both over-abstain |
| WORKER_FAIL | 0/5 | 0/5 | both over-abstain |
| V5_OVERLOAD | 0/5 | 0/5 | both over-abstain (pilot V5 over-abstain **replicates**) |
| LOCATOR_OVERLOAD | 0/5 | 0/5 | both over-abstain |

Pilot raw `SAFE_STOP` on locator **did not replicate** here (GBNF + this case set: abstain, not unsafe).

---

## Tokens and latency

|  | structured | raw |
| --- | --- | --- |
| prompt tokens mean | 761 | 582 |
| prompt chars mean | 1516 | 872 |
| completion tokens mean | 18.8 | 16.9 |
| L2 latency mean | 2185 ms | 1660 ms |

Structured is **longer and slower**. Any quality gain is not from a shorter prompt.

---

## Verdict

**RQ1 SUPPORTED** on this frozen paired set in the limited sense:

> Holding model, tools, seed, and information fixed, structured representation never reduced paired strict success and uniquely recovered all five `CAMERA_STALE` cases that raw abstained on. Unsafe rate was zero for both.

It is **not** a general finding that structured state makes the 4B model a reliable diagnoser. Four families remain joint failures via over-abstain. Serial is already solved (and one shared error) under both views. Do not pool these 30 with the old 16-case pilot.

Error taxonomy dominant class: `over_abstain`. Secondary: one paired `wrong_diagnosis` (`SERIAL_FAIL` state with `connected=true` and `consecutive_failures=2` → `restart_worker`).
