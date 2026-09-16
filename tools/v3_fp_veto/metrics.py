"""Holdout / fixture metrics. Independent of train_pareto.py."""

from __future__ import annotations


def confusion_counts(y_true, y_pred) -> dict:
    tp = fp = tn = fn = 0
    for truth, pred in zip(y_true, y_pred):
        truth_b = int(bool(int(truth)))
        pred_b = int(bool(int(pred)))
        if truth_b and pred_b:
            tp += 1
        elif not truth_b and pred_b:
            fp += 1
        elif not truth_b and not pred_b:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def classification_metrics(y_true, y_pred) -> dict:
    counts = confusion_counts(y_true, y_pred)
    tp, fp, tn, fn = counts["tp"], counts["fp"], counts["tn"], counts["fn"]
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    specificity = 1.0 - fpr
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    q_d = min(recall, specificity)
    return {
        **counts,
        "n": tp + fp + tn + fn,
        "recall": recall,
        "fpr": fpr,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "Q_D": q_d,
        "U": 0.5 + 0.5 * q_d,
    }
