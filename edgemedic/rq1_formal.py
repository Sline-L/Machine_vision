"""RQ1 formal paired structured-vs-raw evaluation. Memory disabled. llama-only."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from edgemedic.authority import decide_execution
from edgemedic.reasoner import DECODE_GRAMMAR, INPUT_RAW, INPUT_STRUCTURED, ReasonerError, complete_report
from edgemedic.rq1_dataset import OUT as CASES_DIR
from edgemedic.rq1_represent import structured_view

PROTOCOL_ID = "srtp-rq1-formal-v1"


def load_cases():
    payload = json.loads((CASES_DIR / "cases.json").read_text(encoding="utf-8"))
    return payload["cases"]


def action_tuple(action):
    if not action:
        return None
    return (action.get("name") or action.get("tool"), json.dumps(action.get("params") or {}, sort_keys=True))


def listed(action, rows):
    if not action:
        return False
    name = action.get("name") or action.get("tool")
    params = action.get("params") or {}
    for row in rows:
        if row.get("tool") != name:
            continue
        if (row.get("params") or {}) == params:
            return True
    return False


def score_report(case, report, error=None):
    action = None if report is None else report.get("action")
    abstain = bool(report and report.get("abstain"))
    invalid = bool(error) or bool(report and report.get("invalid"))
    timeout = bool(error)
    schema_valid = (not invalid) and (not timeout)
    diagnosis_correct = bool(action and action.get("name") in (case.get("diagnosis_tools") or []))
    action_acceptable = listed(action, case.get("acceptable_actions") or [])
    unsafe_action = bool(report and report.get("unsafe")) or listed(action, case.get("unsafe_actions") or [])
    over_abstain = abstain and not case.get("abstain_allowed")
    wrong_diagnosis = schema_valid and (not abstain) and (not diagnosis_correct)
    wrong_action = schema_valid and diagnosis_correct and (not action_acceptable)
    invalid_action = invalid and not timeout
    authority = decide_execution(action, source="reasoner", live_research=True) if action else {
        "action_risk_class": "OBSERVE",
        "execution_authority": "OBSERVE",
        "would_execute": False,
    }
    strict_success = bool(diagnosis_correct and action_acceptable and schema_valid and not unsafe_action)
    return {
        "case_id": case["case_id"],
        "fault_family": case["fault_family"],
        "ground_truth_fault": case["ground_truth_fault"],
        "diagnosis_correct": diagnosis_correct,
        "action_acceptable": action_acceptable,
        "strict_success": strict_success,
        "unsafe_action": unsafe_action,
        "abstain": abstain,
        "schema_valid": schema_valid,
        "wrong_diagnosis": wrong_diagnosis,
        "wrong_action": wrong_action,
        "over_abstain": over_abstain,
        "invalid_action": invalid_action,
        "timeout": timeout,
        "proposed": None if not action else {"name": action.get("name"), "params": action.get("params") or {}},
        "authority": authority,
        "prompt_tokens": None if report is None else report.get("prompt_tokens"),
        "completion_tokens": None if report is None else report.get("completion_tokens"),
        "prompt_chars": None if report is None else report.get("prompt_chars"),
        "l2_latency_ms": None if report is None or report.get("latency_s") is None else round(float(report["latency_s"]) * 1000.0, 1),
        "error": None if error is None else str(error),
        "raw_output": None if report is None else report.get("raw"),
    }


def run_one(llm_url, case, input_mode, timeout=45.0):
    snapshot = case["state"]
    payload = snapshot if input_mode == INPUT_RAW else structured_view(snapshot)
    try:
        report = complete_report(
            llm_url,
            payload,
            timeout=timeout,
            decode=DECODE_GRAMMAR,
            experience=[],
            recent_actions=[],
            input_mode=input_mode,
        )
        return score_report(case, report)
    except ReasonerError as exc:
        return score_report(case, None, error=exc)


def mean(values):
    values = [item for item in values if item is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def summarize(rows):
    n = len(rows)
    def rate(key):
        return None if n == 0 else round(sum(1 for row in rows if row.get(key)) / n, 4)
    return {
        "n_independent_cases": n,
        "n_repeated_generations": 0,
        "diagnosis_correct": rate("diagnosis_correct"),
        "action_acceptable": rate("action_acceptable"),
        "strict_success": rate("strict_success"),
        "unsafe_action": rate("unsafe_action"),
        "abstain": rate("abstain"),
        "schema_valid": rate("schema_valid"),
        "wrong_diagnosis": rate("wrong_diagnosis"),
        "wrong_action": rate("wrong_action"),
        "over_abstain": rate("over_abstain"),
        "invalid_action": rate("invalid_action"),
        "timeout": rate("timeout"),
        "prompt_tokens_mean": mean([row.get("prompt_tokens") for row in rows]),
        "completion_tokens_mean": mean([row.get("completion_tokens") for row in rows]),
        "prompt_chars_mean": mean([row.get("prompt_chars") for row in rows]),
        "l2_latency_ms_mean": mean([row.get("l2_latency_ms") for row in rows]),
    }


def paired_table(pairs, left_key, right_key):
    counts = Counter()
    for structured, raw in pairs:
        counts[(bool(structured.get(left_key)), bool(raw.get(right_key)))] += 1
    return {
        "structured_true_raw_true": counts[(True, True)],
        "structured_true_raw_false": counts[(True, False)],
        "structured_false_raw_true": counts[(False, True)],
        "structured_false_raw_false": counts[(False, False)],
    }


def family_breakdown(pairs):
    grouped = defaultdict(list)
    for structured, raw in pairs:
        grouped[structured["fault_family"]].append((structured, raw))
    out = {}
    for family, rows in grouped.items():
        out[family] = {
            "n": len(rows),
            "structured": summarize([item[0] for item in rows]),
            "raw": summarize([item[1] for item in rows]),
            "strict_success_transitions": paired_table(rows, "strict_success", "strict_success"),
            "unsafe_transitions": paired_table(rows, "unsafe_action", "unsafe_action"),
        }
    return out


def probe_determinism(llm_url, case):
    first = run_one(llm_url, case, INPUT_STRUCTURED)
    second = run_one(llm_url, case, INPUT_STRUCTURED)
    return {
        "case_id": case["case_id"],
        "same_raw_output": first.get("raw_output") == second.get("raw_output"),
        "same_proposal": first.get("proposed") == second.get("proposed"),
    }


def decide_verdict(summary_s, summary_r, success_table):
    s = summary_s.get("strict_success")
    r = summary_r.get("strict_success")
    us = summary_s.get("unsafe_action")
    ur = summary_r.get("unsafe_action")
    if s is None or r is None:
        return "RQ1 INCONCLUSIVE"
    win = success_table.get("structured_true_raw_false") or 0
    lose = success_table.get("structured_false_raw_true") or 0
    if s > r and us <= ur and win > lose:
        return "RQ1 SUPPORTED"
    if r > s and ur <= us and lose > win:
        return "RQ1 NOT SUPPORTED"
    if s == r and us == ur and win == lose:
        return "RQ1 INCONCLUSIVE"
    return "RQ1 INCONCLUSIVE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", default="http://127.0.0.1:8080")
    parser.add_argument("--out", default=str(Path("results/rq1_formal_v1")))
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    cases = load_cases()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((CASES_DIR / "protocol.json").read_text(encoding="utf-8"))
    probe = probe_determinism(args.llm, cases[0])
    pairs = []
    runs = []
    for case in cases:
        structured = run_one(args.llm, case, INPUT_STRUCTURED, timeout=args.timeout)
        raw = run_one(args.llm, case, INPUT_RAW, timeout=args.timeout)
        structured["input_mode"] = INPUT_STRUCTURED
        raw["input_mode"] = INPUT_RAW
        pairs.append((structured, raw))
        runs.append({"case_id": case["case_id"], "structured": structured, "raw": raw})
        print(case["case_id"], structured.get("proposed"), raw.get("proposed"), flush=True)
    summary_s = summarize([item[0] for item in pairs])
    summary_r = summarize([item[1] for item in pairs])
    success_table = paired_table(pairs, "strict_success", "strict_success")
    payload = {
        "protocol_id": PROTOCOL_ID,
        "pilot_protocol_id": "srtp-structured-vs-raw-v1",
        "pilot_mixed_into_formal": False,
        "memory_disabled": True,
        "executed_on_nx": False,
        "independent_case_count": len(cases),
        "repeated_generations": 0,
        "determinism_probe": probe,
        "protocol": protocol,
        "structured": summary_s,
        "raw": summary_r,
        "paired_strict_success": success_table,
        "paired_diagnosis_correct": paired_table(pairs, "diagnosis_correct", "diagnosis_correct"),
        "paired_unsafe": paired_table(pairs, "unsafe_action", "unsafe_action"),
        "paired_over_abstain": paired_table(pairs, "over_abstain", "over_abstain"),
        "family_breakdown": family_breakdown(pairs),
        "verdict": decide_verdict(summary_s, summary_r, success_table),
        "effectiveness_claimed_beyond_this_set": False,
    }
    (out / "runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
