"""One-shot formal capability evaluation against a sealed holdout.

Refuse if candidate hash / weights / threshold / fusion drift from frozen artifact.
Refuse second formal run for the same candidate×holdout unless diagnostic_only.
Never auto-mutates production registry; writes admission_proposal.json on PASS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from gp.capability_v2 import PROFILE_ID, compute_config_hash, load_frozen, validate_frozen_artifacts
from gp.config import PROJECT_ROOT


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _metrics(y_true, y_pred):
    tp = fp = tn = fn = 0
    for truth, pred in zip(y_true, y_pred):
        if truth and pred:
            tp += 1
        elif not truth and pred:
            fp += 1
        elif not truth and not pred:
            tn += 1
        else:
            fn += 1
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
    }


def _lock_path(out_dir: Path) -> Path:
    return out_dir / "evaluation_lock.json"


def formal_evaluate(
    *,
    holdout_manifest: Path,
    predictions_csv: Path,
    out_dir: Path,
    diagnostic_only: bool = False,
    mission_q_d_floor: float = 0.70,
) -> dict:
    """predictions_csv columns: file,score (probability). Labels come from holdout."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not diagnostic_only and _lock_path(out_dir).is_file():
        raise RuntimeError("REFUSE: formal evaluation already locked for this candidate×holdout")

    frozen = load_frozen()
    identity = validate_frozen_artifacts(frozen)
    holdout = json.loads(Path(holdout_manifest).read_text(encoding="utf-8"))
    labels = {row["file"]: row["label"] == "scratch" for row in holdout["images"]}
    scores = {}
    with Path(predictions_csv).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            scores[row["file"]] = float(row["score"])
    missing = sorted(set(labels) - set(scores))
    if missing:
        raise ValueError(f"predictions missing {len(missing)} files, e.g. {missing[:3]}")

    threshold = float(frozen["threshold"])
    y_true = []
    y_pred = []
    for name in sorted(labels):
        y_true.append(labels[name])
        y_pred.append(scores[name] >= threshold)
    metrics = _metrics(y_true, y_pred)
    dataset_target_pass = metrics["recall"] >= 0.95 and metrics["fpr"] <= 0.20
    mission_contract_pass = metrics["Q_D"] >= float(mission_q_d_floor)

    result = {
        "mode": "DIAGNOSTIC_ONLY" if diagnostic_only else "FORMAL",
        "profile_id": PROFILE_ID,
        "candidate_id": frozen.get("candidate_id"),
        "candidate_config_hash": identity["config_hash"],
        "classifier_sha": identity["classifier_sha"],
        "detector_sha": identity["detector_sha"],
        "threshold": threshold,
        "fusion_alpha": identity["fusion_alpha"],
        "holdout_dataset_id": holdout.get("dataset_id"),
        "holdout_sha256": holdout.get("dataset_sha256"),
        "metrics": metrics,
        "dataset_target_pass": dataset_target_pass,
        "mission_contract_pass": mission_contract_pass,
        "runtime_gate": "OPEN" if mission_contract_pass and not diagnostic_only else "CLOSED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    result_hash = _sha256_text(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    result["result_hash"] = result_hash

    if diagnostic_only:
        path = out_dir / "diagnostic_result.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    (out_dir / "formal_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lock = {
        "dataset_hash": holdout.get("dataset_sha256"),
        "candidate_hash": identity["config_hash"],
        "timestamp": result["timestamp"],
        "result_hash": result_hash,
        "mission_contract_pass": mission_contract_pass,
    }
    _lock_path(out_dir).write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if mission_contract_pass:
        proposal = {
            "profile_id": PROFILE_ID,
            "mission_approved_candidate": True,
            "candidate_hash": identity["config_hash"],
            "holdout_hash": holdout.get("dataset_sha256"),
            "evidence_refs": [
                str(out_dir / "formal_result.json"),
                str(_lock_path(out_dir)),
                str(PROJECT_ROOT / "docs/capability-extraction/v3/latency_degraded_v2_effnet_det.frozen.json"),
            ],
            "notes": "Explicit integration step required to set registry.mission_approved=true",
        }
        (out_dir / "admission_proposal.json").write_text(
            json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Formal one-shot Scratch capability evaluation")
    parser.add_argument("--holdout-manifest", required=True, type=Path)
    parser.add_argument("--predictions-csv", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--diagnostic-only", action="store_true")
    parser.add_argument("--mission-q-d-floor", type=float, default=0.70)
    args = parser.parse_args(argv)
    result = formal_evaluate(
        holdout_manifest=args.holdout_manifest,
        predictions_csv=args.predictions_csv,
        out_dir=args.out_dir,
        diagnostic_only=args.diagnostic_only,
        mission_q_d_floor=args.mission_q_d_floor,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
