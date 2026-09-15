#!/usr/bin/env python3
"""V3-1: train/val Pareto for lightweight FP veto on existing features.

EXPLORATION — NOT MISSION APPROVED.
Select on val only. Never read test_scratch / holdout.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

BANNER = "V3-1 FP-VETO PARETO — train/val ONLY — NOT MISSION APPROVED"
MISSION_QD_FLOOR = 0.70
FEATURE_NAMES = [
    "cls1",
    "det",
    "fused_v2",
    "n_boxes",
    "sum_conf",
    "mean_conf",
    "top1_conf",
    "top2_conf",
    "top3_conf",
    "cls_minus_det",
    "log1p_boxes",
    "raw_cls",
    "raw_det",
]


def metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    specificity = 1.0 - fpr
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    q_d = min(recall, specificity)
    u = 0.5 + 0.5 * q_d
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "recall": recall,
        "fpr": fpr,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "Q_D": q_d,
        "U": u,
        "mission_qd_pass": q_d >= MISSION_QD_FLOOR,
    }


def load_rows(path: Path):
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if r["split"] not in {"train_scratch", "val_scratch"}:
            raise SystemExit(f"forbidden split in features: {r['split']}")
    return rows


def matrix(rows, names=FEATURE_NAMES):
    x = np.asarray([[float(r[n]) for n in names] for r in rows], dtype=np.float64)
    y = np.asarray([int(r["label"]) for r in rows], dtype=np.int64)
    return x, y


def standardize_fit(x):
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    return mean, std


def standardize_apply(x, mean, std):
    return (x - mean) / std


def sigmoid(z):
    z = np.clip(z, -30, 30)
    return 1.0 / (1.0 + np.exp(-z))


@dataclass
class LogisticModel:
    weights: np.ndarray
    bias: float
    mean: np.ndarray
    std: np.ndarray
    feature_names: list

    def predict_proba(self, x):
        xs = standardize_apply(x, self.mean, self.std)
        return sigmoid(xs @ self.weights + self.bias)


def train_logistic(x, y, l2=1e-2, steps=4000, lr=0.2, seed=0):
    rng = np.random.default_rng(seed)
    mean, std = standardize_fit(x)
    xs = standardize_apply(x, mean, std)
    n, d = xs.shape
    w = rng.normal(0, 0.01, size=d)
    b = 0.0
    for _ in range(steps):
        p = sigmoid(xs @ w + b)
        err = p - y
        grad_w = (xs.T @ err) / n + l2 * w
        grad_b = float(err.mean())
        w -= lr * grad_w
        b -= lr * grad_b
    return LogisticModel(w, b, mean, std, FEATURE_NAMES)


@dataclass
class TinyMLP:
    w1: np.ndarray
    b1: np.ndarray
    w2: np.ndarray
    b2: float
    mean: np.ndarray
    std: np.ndarray

    def predict_proba(self, x):
        xs = standardize_apply(x, self.mean, self.std)
        h = np.tanh(xs @ self.w1 + self.b1)
        return sigmoid(h @ self.w2 + self.b2)


def train_mlp(x, y, hidden=16, l2=1e-3, steps=6000, lr=0.05, seed=0):
    rng = np.random.default_rng(seed)
    mean, std = standardize_fit(x)
    xs = standardize_apply(x, mean, std)
    n, d = xs.shape
    w1 = rng.normal(0, 0.05, size=(d, hidden))
    b1 = np.zeros(hidden)
    w2 = rng.normal(0, 0.05, size=hidden)
    b2 = 0.0
    for _ in range(steps):
        h_pre = xs @ w1 + b1
        h = np.tanh(h_pre)
        logits = h @ w2 + b2
        p = sigmoid(logits)
        err = p - y
        # grads
        dlogits = err / n
        dw2 = h.T @ dlogits + l2 * w2
        db2 = float(dlogits.sum())
        dh = np.outer(dlogits, w2) * (1.0 - h**2)
        dw1 = xs.T @ dh + l2 * w1
        db1 = dh.sum(axis=0)
        w2 -= lr * dw2
        b2 -= lr * db2
        w1 -= lr * dw1
        b1 -= lr * db1
    return TinyMLP(w1, b1, w2, b2, mean, std)


def sweep_threshold(proba, y, mode_name, model_name):
    """Sweep decision thresholds; return best Mission Q_D and Pareto front."""
    candidates = []
    for thr in np.linspace(0.05, 0.95, 181):
        pred = (proba >= thr).astype(int)
        m = metrics(y, pred)
        m.update({"threshold": float(thr), "mode": mode_name, "model": model_name})
        candidates.append(m)
    # best by Q_D then lower FPR
    best = max(candidates, key=lambda m: (m["Q_D"], -m["fpr"], m["recall"]))
    # light Pareto: keep non-dominated on (Q_D, -FPR)
    pareto = []
    for m in sorted(candidates, key=lambda z: -z["Q_D"]):
        if not pareto or m["fpr"] < pareto[-1]["fpr"] - 1e-12:
            pareto.append(m)
    return best, candidates, pareto


def baseline_v2(rows):
    y = [int(r["label"]) for r in rows]
    pred = [int(r["v2_reject"]) for r in rows]
    return metrics(y, pred)


def veto_gate_scores(rows, proba, gate_thr=None):
    """Two-stage: keep V2 PASS; if V2 REJECT, allow veto to PASS when P(scratch) low.

    final_reject = v2_reject AND (proba >= gate_thr)
    """
    if gate_thr is None:
        # will sweep outside
        raise ValueError("gate_thr required")
    y = np.asarray([int(r["label"]) for r in rows])
    v2 = np.asarray([int(r["v2_reject"]) for r in rows])
    pred = ((v2 == 1) & (proba >= gate_thr)).astype(int)
    return metrics(y, pred), pred


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(BANNER, flush=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args.features)
    train = [r for r in rows if r["split"] == "train_scratch"]
    val = [r for r in rows if r["split"] == "val_scratch"]
    x_tr, y_tr = matrix(train)
    x_va, y_va = matrix(val)

    report = {
        "banner": BANNER,
        "mission_qd_floor": MISSION_QD_FLOOR,
        "n_train": len(train),
        "n_val": len(val),
        "feature_names": FEATURE_NAMES,
        "baselines": {
            "v2_train": baseline_v2(train),
            "v2_val": baseline_v2(val),
        },
        "candidates": [],
        "selection": None,
        "latency_note": (
            "V3-1 adds only a tiny logistic/MLP on already-computed features; "
            "expected extra integrated p95 << 1 ms (well under S1 10–12 ms budget). "
            "NX S1 remeasure required before freeze."
        ),
        "forbidden": ["test_scratch", "fresh_holdout", "production_registry"],
    }

    models = {
        "logistic_l2_1e-2": train_logistic(x_tr, y_tr, l2=1e-2, seed=0),
        "logistic_l2_1e-1": train_logistic(x_tr, y_tr, l2=1e-1, seed=1),
        "mlp_h16": train_mlp(x_tr, y_tr, hidden=16, seed=2),
        "mlp_h8": train_mlp(x_tr, y_tr, hidden=8, seed=3),
    }

    all_val_best = []
    for name, model in models.items():
        p_tr = model.predict_proba(x_tr)
        p_va = model.predict_proba(x_va)

        # Mode A: replace score entirely
        best_a, _, pareto_a = sweep_threshold(p_va, y_va, "replace_score", name)
        best_a_tr, _, _ = sweep_threshold(p_tr, y_tr, "replace_score", name)
        entry_a = {
            "model": name,
            "mode": "replace_score",
            "val_best": best_a,
            "train_at_val_threshold": metrics(y_tr, (p_tr >= best_a["threshold"]).astype(int)),
            "train_best_qd": best_a_tr["Q_D"],
            "pareto_val_size": len(pareto_a),
        }
        report["candidates"].append(entry_a)
        all_val_best.append(entry_a)

        # Mode B: V2 reject gate + learned P(scratch) veto
        best_b = None
        for thr in np.linspace(0.05, 0.95, 181):
            m, _ = veto_gate_scores(val, p_va, gate_thr=float(thr))
            m.update({"threshold": float(thr), "mode": "v2_reject_and_proba", "model": name})
            if best_b is None or (m["Q_D"], -m["fpr"], m["recall"]) > (
                best_b["Q_D"],
                -best_b["fpr"],
                best_b["recall"],
            ):
                best_b = m
        assert best_b is not None
        m_tr, _ = veto_gate_scores(train, p_tr, gate_thr=best_b["threshold"])
        entry_b = {
            "model": name,
            "mode": "v2_reject_and_proba",
            "val_best": best_b,
            "train_at_val_threshold": m_tr,
        }
        report["candidates"].append(entry_b)
        all_val_best.append(entry_b)

    # Select primary: max val Q_D among mission-pass if any; else max Q_D; prefer lower FPR vs V2
    v2_val = report["baselines"]["v2_val"]
    ranked = sorted(
        all_val_best,
        key=lambda e: (
            int(e["val_best"]["mission_qd_pass"]),
            e["val_best"]["Q_D"],
            -e["val_best"]["fpr"],
            e["val_best"]["recall"],
        ),
        reverse=True,
    )
    primary = ranked[0]
    improved = primary["val_best"]["Q_D"] > v2_val["Q_D"] + 0.01 and primary["val_best"]["fpr"] < v2_val["fpr"] - 0.01
    mission_ok = primary["val_best"]["mission_qd_pass"]
    report["selection"] = {
        "primary": primary,
        "improved_vs_v2_val": improved,
        "mission_qd_pass_val": mission_ok,
        "delta_qd_vs_v2": primary["val_best"]["Q_D"] - v2_val["Q_D"],
        "delta_fpr_vs_v2": primary["val_best"]["fpr"] - v2_val["fpr"],
        "freeze_decision": None,
        "next_step": None,
    }
    if mission_ok and improved:
        report["selection"]["freeze_decision"] = "V3-1 CANDIDATE PROMISING — freeze pending NX S1 latency confirm"
        report["selection"]["next_step"] = "remeasure S1 p95; if <190 freeze V3-1 primary"
    elif improved:
        report["selection"]["freeze_decision"] = "V3-1 PARTIAL — FP improved but Mission Q_D floor not met on val"
        report["selection"]["next_step"] = "continue V3-1 variants OR proceed to V3-2 distillation"
    else:
        report["selection"]["freeze_decision"] = "V3-1 NOT SUFFICIENT on val — proceed to V3-2 FP-veto distillation"
        report["selection"]["next_step"] = "V3-2"

    # Persist model weights for primary if logistic/mlp
    sel_model_name = primary["model"]
    sel_model = models[sel_model_name]
    if isinstance(sel_model, LogisticModel):
        payload = {
            "type": "logistic",
            "weights": sel_model.weights.tolist(),
            "bias": sel_model.bias,
            "mean": sel_model.mean.tolist(),
            "std": sel_model.std.tolist(),
            "feature_names": FEATURE_NAMES,
            "mode": primary["mode"],
            "threshold": primary["val_best"]["threshold"],
        }
    else:
        payload = {
            "type": "mlp",
            "w1": sel_model.w1.tolist(),
            "b1": sel_model.b1.tolist(),
            "w2": sel_model.w2.tolist(),
            "b2": sel_model.b2,
            "mean": sel_model.mean.tolist(),
            "std": sel_model.std.tolist(),
            "feature_names": FEATURE_NAMES,
            "mode": primary["mode"],
            "threshold": primary["val_best"]["threshold"],
        }
    (args.out_dir / "primary_veto_model.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (args.out_dir / "pareto_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Markdown summary
    lines = [
        "# V3-1 lightweight FP-veto — train/val Pareto",
        "",
        "```text",
        BANNER,
        "fresh holdout: NOT USED",
        "test_scratch: NOT USED",
        "```",
        "",
        "## Baselines (V2 topology + frozen threshold)",
        "",
        f"- train Q_D={v2_val and report['baselines']['v2_train']['Q_D']:.4f} FPR={report['baselines']['v2_train']['fpr']:.4f}",
        f"- val   Q_D={report['baselines']['v2_val']['Q_D']:.4f} FPR={report['baselines']['v2_val']['fpr']:.4f}",
        "",
        "## Primary selection",
        "",
        f"- model: `{primary['model']}`",
        f"- mode: `{primary['mode']}`",
        f"- val Q_D={primary['val_best']['Q_D']:.4f} FPR={primary['val_best']['fpr']:.4f} "
        f"recall={primary['val_best']['recall']:.4f}",
        f"- ΔQ_D vs V2 val: {report['selection']['delta_qd_vs_v2']:+.4f}",
        f"- ΔFPR vs V2 val: {report['selection']['delta_fpr_vs_v2']:+.4f}",
        f"- Mission Q_D≥0.70: {mission_ok}",
        "",
        f"**Decision:** {report['selection']['freeze_decision']}",
        "",
        f"**Next:** {report['selection']['next_step']}",
        "",
        "## Latency",
        "",
        report["latency_note"],
        "",
    ]
    (args.out_dir / "pareto_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["selection"], indent=2), flush=True)
    print(f"wrote {args.out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
