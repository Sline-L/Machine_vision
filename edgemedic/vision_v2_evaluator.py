"""Unified lightweight capability evaluator (val-only, design/exploratory).

Reuses train_scratch_v5.choose_threshold (PRIMARY_FPR_CAP=0.20).
Refuses test_scratch paths. Does not open runtime profiles.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PRIMARY_FPR_CAP = 0.20
FPR_CAPS = (0.10, 0.20, 0.30, 0.50)
LOCKED_MARKERS = ("test_scratch",)


def refuse_locked(path: Path) -> None:
    text = str(path).replace("\\", "/")
    for marker in LOCKED_MARKERS:
        if marker in text:
            raise ValueError(f"refusing locked path: {path}")


def choose_threshold(labels: list[int], probabilities: list[float], fpr_cap: float):
    candidates = sorted({0.0, 1.0, *probabilities})
    best = None
    for threshold in candidates:
        guesses = [value >= threshold for value in probabilities]
        tp = sum(actual == 1 and guess for actual, guess in zip(labels, guesses))
        fp = sum(actual == 0 and guess for actual, guess in zip(labels, guesses))
        tn = sum(actual == 0 and not guess for actual, guess in zip(labels, guesses))
        fn = sum(actual == 1 and not guess for actual, guess in zip(labels, guesses))
        recall = tp / max(1, tp + fn)
        precision = tp / max(1, tp + fp)
        fpr = fp / max(1, fp + tn)
        row = {
            "threshold": float(threshold),
            "recall": recall,
            "precision": precision,
            "f1": 2 * precision * recall / max(1e-9, precision + recall),
            "fpr": fpr,
            "specificity": 1 - fpr,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        }
        key = (fpr <= fpr_cap, recall, -fpr, precision)
        if best is None or key > best[0]:
            best = (key, row)
    assert best is not None
    return best[1], best[0]


def q_d_u(recall: float, fpr: float):
    spec = 1.0 - fpr
    qd = min(recall, spec)
    u = 0.5 + 0.5 * qd
    return qd, u


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(path: Path) -> list[dict]:
    refuse_locked(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@dataclass
class ValSample:
    stem: str
    label: int
    truth: str
    full: float
    cls_mean: float
    cls1: float
    cls2: float
    detector: float


def load_merged_val(full_csv: Path, cls_csv: Path) -> list[ValSample]:
    refuse_locked(full_csv)
    refuse_locked(cls_csv)
    full_rows = {r["stem"]: r for r in load_csv(full_csv)}
    cls_rows = {r["stem"]: r for r in load_csv(cls_csv)}
    keys = sorted(set(full_rows) & set(cls_rows))
    if not keys:
        raise ValueError("no overlapping val stems between full and classifier CSVs")
    out = []
    for stem in keys:
        fr, cr = full_rows[stem], cls_rows[stem]
        label = int(cr["label"])
        cls_mean = float(cr["classifier_mean"])
        full_score = float(fr["scratch_probability"])
        detector = (full_score - 0.25 * cls_mean) / 0.75
        out.append(
            ValSample(
                stem=stem,
                label=label,
                truth=cr.get("truth") or fr.get("truth") or ("scratch" if label else "normal"),
                full=full_score,
                cls_mean=cls_mean,
                cls1=float(cr["classifier_1"]),
                cls2=float(cr["classifier_2"]),
                detector=detector,
            )
        )
    return out


def fuse_weighted(classifier_score: float, detector_score: float, alpha: float) -> float:
    return alpha * classifier_score + (1.0 - alpha) * detector_score


def fuse_soft_or(classifier_score: float, detector_score: float) -> float:
    return max(classifier_score, detector_score)


def evaluate_candidate(
    name: str,
    samples: list[ValSample],
    probabilities: list[float],
    *,
    components: str,
    fusion: str,
    semantic_loss: str,
    latency_p95_ms: float | None = None,
    latency_relative: float | None = None,
    notes: str = "",
) -> dict:
    labels = [s.label for s in samples]
    primary, selection_key = choose_threshold(labels, probabilities, PRIMARY_FPR_CAP)
    qd, u = q_d_u(primary["recall"], primary["fpr"])
    target_met = primary["recall"] >= 0.95 and primary["fpr"] <= PRIMARY_FPR_CAP
    return {
        "candidate_id": name,
        "components": components,
        "fusion": fusion,
        "semantic_loss": semantic_loss,
        "threshold": primary["threshold"],
        "selection_key": list(selection_key),
        "recall": round(primary["recall"], 4),
        "fpr": round(primary["fpr"], 4),
        "specificity": round(primary["specificity"], 4),
        "precision": round(primary["precision"], 4),
        "f1": round(primary["f1"], 4),
        "Q_D_val": round(qd, 4),
        "U_val": round(u, 4),
        "target_met": target_met,
        "tp": primary["tp"],
        "fp": primary["fp"],
        "tn": primary["tn"],
        "fn": primary["fn"],
        "latency_p95_ms": latency_p95_ms,
        "latency_relative_full": latency_relative,
        "notes": notes,
    }


def build_candidates(samples: list[ValSample], latency_table: dict) -> list[dict]:
    labels = [s.label for s in samples]

    def probs(fn):
        return [fn(s) for s in samples]

    specs = [
        ("FULL_a0.25_mean", lambda s: s.full, "cls1+cls2+det@960", "weighted α=0.25 classifier_mean", "none", "FULL"),
        ("classifier_mean", lambda s: s.cls_mean, "cls1+cls2", "classifier_mean", "bbox auxiliary", "CLS_ONLY"),
        ("effnet_only", lambda s: s.cls1, "cls1 EffNet@384", "classifier", "bbox", "CLS1"),
        ("resnet_only", lambda s: s.cls2, "cls2 ResNet@384", "classifier", "bbox", "CLS2"),
        ("detector_only", lambda s: s.detector, "det P2@960", "detector", "bbox preserved", "DET"),
        ("effnet_det_a0.25", lambda s: fuse_weighted(s.cls1, s.detector, 0.25), "cls1+det", "weighted α=0.25", "bbox", "EFFNET_DET_25"),
        ("effnet_det_a0.50", lambda s: fuse_weighted(s.cls1, s.detector, 0.50), "cls1+det", "weighted α=0.50", "bbox", "EFFNET_DET_50"),
        ("effnet_det_a0.75", lambda s: fuse_weighted(s.cls1, s.detector, 0.75), "cls1+det", "weighted α=0.75", "bbox", "EFFNET_DET_75"),
        ("mean_det_a0.50", lambda s: fuse_weighted(s.cls_mean, s.detector, 0.50), "cls1+cls2+det", "weighted α=0.50 mean", "bbox", "MEAN_DET_50"),
        ("mean_det_a0.75", lambda s: fuse_weighted(s.cls_mean, s.detector, 0.75), "cls1+cls2+det", "weighted α=0.75 mean", "bbox", "MEAN_DET_75"),
        ("soft_or_mean", lambda s: fuse_soft_or(s.cls_mean, s.detector), "cls1+cls2+det", "soft_or mean+det", "bbox", "SOFT_OR"),
        ("soft_or_effnet", lambda s: fuse_soft_or(s.cls1, s.detector), "cls1+det", "soft_or effnet+det", "bbox", "SOFT_OR_EFF"),
    ]
    rows = []
    full_p95 = latency_table.get("FULL", {}).get("p95")
    for name, fn, components, fusion, semantic, lat_key in specs:
        lat = latency_table.get(lat_key, {})
        rel = None if full_p95 in (None, 0) or lat.get("p95") is None else round(lat["p95"] / full_p95, 3)
        rows.append(
            evaluate_candidate(
                name,
                samples,
                probs(fn),
                components=components,
                fusion=fusion,
                semantic_loss=semantic,
                latency_p95_ms=lat.get("p95"),
                latency_relative=rel,
            )
        )
    return rows


def pareto_class(rows: list[dict]) -> list[dict]:
    """Mark dominated / pareto / primary by val Q_D and latency (lower better)."""
    out = []
    for i, a in enumerate(rows):
        dominated = False
        for j, b in enumerate(rows):
            if i == j:
                continue
            q_better = b["Q_D_val"] >= a["Q_D_val"]
            lat_better = (
                b.get("latency_p95_ms") is None
                or a.get("latency_p95_ms") is None
                or b["latency_p95_ms"] <= a["latency_p95_ms"]
            )
            strict = q_better and lat_better and (
                b["Q_D_val"] > a["Q_D_val"]
                or (
                    b.get("latency_p95_ms") is not None
                    and a.get("latency_p95_ms") is not None
                    and b["latency_p95_ms"] < a["latency_p95_ms"]
                )
            )
            if strict:
                dominated = True
                break
        tag = "DOMINATED" if dominated else "PARETO"
        row = dict(a)
        row["pareto_tag"] = tag
        out.append(row)
    return out


def pick_primary(rows: list[dict]) -> dict | None:
    """Best val target met with real workload reduction (single cls + det preferred)."""
    eligible = [
        r
        for r in rows
        if r.get("target_met")
        and r["pareto_tag"] == "PARETO"
        and "det" in r["components"].lower()
        and r["candidate_id"] not in ("FULL_a0.25_mean", "classifier_mean")
        and "cls1+cls2+det" not in r["components"]
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda r: (r["Q_D_val"], -(r.get("latency_p95_ms") or 1e9)),
    )


def default_latency_estimates() -> dict:
    """Component-based estimates from sealed latency probe (exploratory).

    Paths that still run cls1+cls2+det must not claim large latency wins.
    """
    full_p95 = 275.646
    cls_only = 61.974
    det_p95 = 214.428
    cls1_p95 = 38.749
    cls2_p95 = 27.665
    # cls1+det: remove cls2 only → ~full - cls2 (sequential stage-sum proxy)
    effnet_det_p95 = round(full_p95 - cls2_p95, 3)
    return {
        "FULL": {"p50": 117.62, "p95": full_p95},
        "CLS_ONLY": {"p50": 46.503, "p95": cls_only},
        "CLS1": {"p50": 29.201, "p95": cls1_p95},
        "CLS2": {"p50": 18.69, "p95": cls2_p95},
        "DET": {"p50": 67.895, "p95": det_p95},
        "EFFNET_DET_25": {"p50": None, "p95": effnet_det_p95},
        "EFFNET_DET_50": {"p50": None, "p95": effnet_det_p95},
        "EFFNET_DET_75": {"p50": None, "p95": effnet_det_p95},
        "MEAN_DET_50": {"p50": 117.62, "p95": full_p95},
        "MEAN_DET_75": {"p50": 117.62, "p95": full_p95},
        "SOFT_OR": {"p50": 117.62, "p95": full_p95},
        "SOFT_OR_EFF": {"p50": None, "p95": effnet_det_p95},
    }


def run_evaluation(
    full_csv: Path,
    cls_csv: Path,
    out_dir: Path,
    *,
    latency_table: dict | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = load_merged_val(full_csv, cls_csv)
    latency_table = latency_table or default_latency_estimates()
    rows = build_candidates(samples, latency_table)
    rows = pareto_class(rows)
    primary = pick_primary(rows)
    if primary:
        for row in rows:
            if row["candidate_id"] == primary["candidate_id"]:
                row["pareto_tag"] = "PRIMARY_CANDIDATE"
    payload = {
        "evaluator": "vision_v2_evaluator",
        "claim": "exploratory_val_only",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "full_csv": str(full_csv),
        "cls_csv": str(cls_csv),
        "full_csv_sha256": file_sha256(full_csv),
        "cls_csv_sha256": file_sha256(cls_csv),
        "n_val": len(samples),
        "selection_rule": {
            "PRIMARY_FPR_CAP": PRIMARY_FPR_CAP,
            "key": ["fpr<=cap", "recall", "-fpr", "precision"],
        },
        "detector_scores": "back-calculated from FULL weighted α=0.25 mean fusion",
        "candidates": rows,
        "primary_candidate": primary,
        "fresh_holdout": "NOT_EVALUATED",
    }
    (out_dir / "pareto_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
