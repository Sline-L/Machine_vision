"""Mechanical V3-1 fresh-holdout adjudication.

Implements the original numeric gates plus the pre-holdout amendment:

FAIL-A/B/C are non-exclusive flags.
any FAIL -> overall FAIL
else all mechanical PASS conditions -> PASS
else INCONCLUSIVE

Does not invent soft-pass categories. Does not auto-evaluate narrative clauses.
"""

from __future__ import annotations

QD_FLOOR = 0.70
QD_IMPROVEMENT_MIN = 0.02
FPR_REDUCTION_PASS_MIN = 0.03
FPR_REDUCTION_FAIL_B_LT = 0.02
RECALL_DROP_MAX = 0.08


def _flag_easy_high_confidence(rows: list[dict]) -> dict:
    """Locked operational definition (secondary; does not trigger FAIL-A).

    easy/high-confidence scratch:
      ground_truth == 1 AND full_prediction == 1 AND v2_prediction == 1
    i.e. both frozen operating points already call the sample a scratch.
    """
    easy = 0
    easy_fn = 0
    for row in rows:
        if int(row["ground_truth"]) != 1:
            continue
        if int(row["full_prediction"]) == 1 and int(row["v2_prediction"]) == 1:
            easy += 1
            if int(row["v3_1_prediction"]) == 0:
                easy_fn += 1
    rate = (easy_fn / easy) if easy else 0.0
    return {
        "definition": (
            "ground_truth==1 AND full_prediction==1 AND v2_prediction==1 "
            "(both FULL and V2 operating points already predict scratch)"
        ),
        "easy_high_confidence_scratch_n": easy,
        "fn_on_easy_high_confidence_n": easy_fn,
        "fn_on_easy_high_confidence_rate": rate,
        "triggers_FAIL_A": False,
        "status": "SECONDARY_MANUAL_REVIEW_FLAG",
    }


def adjudicate(
    *,
    metrics_full: dict,
    metrics_v2: dict,
    metrics_v3_1: dict,
    per_sample_rows: list[dict] | None = None,
) -> dict:
    qd_full = float(metrics_full["Q_D"])
    qd_v2 = float(metrics_v2["Q_D"])
    qd_v31 = float(metrics_v3_1["Q_D"])
    fpr_v2 = float(metrics_v2["fpr"])
    fpr_v31 = float(metrics_v3_1["fpr"])
    rec_v2 = float(metrics_v2["recall"])
    rec_v31 = float(metrics_v3_1["recall"])

    qd_delta = qd_v31 - qd_v2
    fpr_reduction = fpr_v2 - fpr_v31
    recall_drop = rec_v2 - rec_v31
    qd_gap_vs_full = qd_full - qd_v31

    pass_conditions = {
        "Q_D_floor": {
            "rule": "Q_D(V3-1) >= 0.70",
            "value": qd_v31,
            "threshold": QD_FLOOR,
            "pass": qd_v31 >= QD_FLOOR,
        },
        "Q_D_improvement": {
            "rule": "Q_D(V3-1) - Q_D(V2) >= 0.02",
            "value": qd_delta,
            "threshold": QD_IMPROVEMENT_MIN,
            "pass": qd_delta >= QD_IMPROVEMENT_MIN,
        },
        "FPR_reduction": {
            "rule": "FPR(V2) - FPR(V3-1) >= 0.03",
            "value": fpr_reduction,
            "threshold": FPR_REDUCTION_PASS_MIN,
            "pass": fpr_reduction >= FPR_REDUCTION_PASS_MIN,
        },
        "recall_drop_limit": {
            "rule": "Recall(V2) - Recall(V3-1) <= 0.08",
            "value": recall_drop,
            "threshold": RECALL_DROP_MAX,
            "pass": recall_drop <= RECALL_DROP_MAX,
        },
        "FULL_collapse_rule": {
            "rule": (
                "Not a mechanical gate. Secondary flag only: report Q_D(FULL)-Q_D(V3-1). "
                "Human narrative review after CONSUMED lock; cannot change overall."
            ),
            "value": qd_gap_vs_full,
            "pass": None,
            "mechanical": False,
        },
    }

    fail_a_recall = recall_drop > RECALL_DROP_MAX
    fail_b_fpr = fpr_reduction < FPR_REDUCTION_FAIL_B_LT
    fail_b_qd = qd_v31 <= qd_v2
    fail_c = qd_v31 < QD_FLOOR

    failure_flags = {
        "FAIL_A": bool(fail_a_recall),
        "FAIL_B": bool(fail_b_fpr or fail_b_qd),
        "FAIL_C": bool(fail_c),
    }
    failure_details = {
        "FAIL_A": {"recall_drop_exceeds_0_08": fail_a_recall},
        "FAIL_B": {
            "fpr_reduction_lt_0_02": fail_b_fpr,
            "Q_D_v3_1_not_greater_than_v2": fail_b_qd,
        },
        "FAIL_C": {"Q_D_below_0_70": fail_c},
    }

    mechanical_pass_ok = all(
        pass_conditions[key]["pass"] is True
        for key in ("Q_D_floor", "Q_D_improvement", "FPR_reduction", "recall_drop_limit")
    )
    any_fail = any(failure_flags.values())
    if any_fail:
        overall = "FAIL"
    elif mechanical_pass_ok:
        overall = "PASS"
    else:
        overall = "INCONCLUSIVE"

    rows = per_sample_rows or []
    easy_flag = _flag_easy_high_confidence(rows) if rows else {
        "status": "SECONDARY_MANUAL_REVIEW_FLAG",
        "note": "no per-sample rows supplied",
        "triggers_FAIL_A": False,
    }

    return {
        "overall": overall,
        "pass_conditions": pass_conditions,
        "failure_flags": failure_flags,
        "failure_details": failure_details,
        "manual_review_flags": {
            "easy_high_confidence_fn": easy_flag,
            "collapse_vs_FULL": {
                "definition": (
                    "Not mechanically adjudicated. Record Q_D(FULL)-Q_D(V3-1) only. "
                    "Narrative domain-gap review is post-lock and cannot rewrite overall."
                ),
                "Q_D_FULL": qd_full,
                "Q_D_V3_1": qd_v31,
                "Q_D_FULL_minus_V3_1": qd_gap_vs_full,
                "triggers_overall": False,
                "status": "SECONDARY_MANUAL_REVIEW_FLAG",
            },
        },
        "deltas": {
            "Q_D_v3_1_minus_v2": qd_delta,
            "FPR_v2_minus_v3_1": fpr_reduction,
            "Recall_v2_minus_v3_1": recall_drop,
        },
        "amendment": {
            "name": "PRE-HOLDOUT PREREGISTRATION AMENDMENT",
            "fresh_holdout_status_at_amendment": "UNTOUCHED",
            "fail_flags_non_exclusive": True,
            "overall_rule": (
                "any FAIL flag -> FAIL; else all mechanical PASS conditions -> PASS; "
                "else INCONCLUSIVE"
            ),
        },
    }
