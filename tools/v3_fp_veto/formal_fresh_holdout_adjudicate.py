#!/usr/bin/env python3
"""One-shot V3-1 fresh-holdout adjudication orchestrator.

candidate_commit is always e8b2b0f. This file lives on the tooling branch only.
Does not load development trainers. Does not fit, sweep, or mutate registry.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from v3_fp_veto.adjudication import adjudicate  # noqa: E402
from v3_fp_veto.frozen_inference import (  # noqa: E402
    CANDIDATE_COMMIT,
    V3_1_MODE,
    V3_1_THRESHOLD,
    apply_veto_to_feature_row,
    load_frozen_veto,
    load_full_threshold,
    load_v2_threshold,
    score_full,
    score_v2,
    score_v3_1,
)
from v3_fp_veto.metrics import classification_metrics  # noqa: E402

_BANNED = (
    "train_pareto",
    "train_logistic",
    "train_mlp",
    "standardize_fit",
    "sweep_threshold",
)


def _assert_no_training_imports() -> None:
    for name in _BANNED:
        if name in sys.modules:
            raise RuntimeError(f"REFUSE: training module loaded: {name}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=str(ROOT), text=True).strip()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _metrics_payload(arm: str, metrics: dict, threshold: float, semantics: str) -> dict:
    return {
        "arm": arm,
        "threshold": threshold,
        "score_semantics": semantics,
        **metrics,
    }


def _write_consumed_lock(out_dir: Path, payload: dict) -> None:
    _write_json(out_dir / "evaluation_lock.json", payload)


def _adjudicator_commit() -> str:
    try:
        return _git(["rev-parse", "HEAD"])
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def run_from_feature_csv(
    *,
    feature_csv: Path,
    out_dir: Path,
    split: str = "val_scratch",
) -> dict:
    """Non-holdout dry run: frozen V2 labels in CSV + frozen V3-1 logistic."""
    _assert_no_training_imports()
    out_dir.mkdir(parents=True, exist_ok=True)
    veto = load_frozen_veto()
    v2_thr = load_v2_threshold()
    with feature_csv.open(encoding="utf-8") as handle:
        rows_in = list(csv.DictReader(handle))
    selected = [r for r in rows_in if r.get("split") == split]
    if not selected:
        raise ValueError(f"no rows for split={split}")
    y_true = []
    y_v2 = []
    y_v31 = []
    per = []
    for row in selected:
        applied = apply_veto_to_feature_row(row, veto, v2_threshold=v2_thr)
        truth = int(row["label"])
        y_true.append(truth)
        y_v2.append(int(applied["v2_prediction"]))
        y_v31.append(int(applied["prediction"]))
        per.append(
            {
                "sample_id": row.get("image") or row.get("sample_id"),
                "ground_truth": truth,
                "full_score": "",
                "full_prediction": "",
                "v2_score": float(row["fused_v2"]),
                "v2_prediction": int(applied["v2_prediction"]),
                "v3_1_score": applied["score"],
                "v3_1_prediction": applied["prediction"],
                "veto_probability": applied["veto_probability"],
                "veto_triggered": applied["veto_triggered"],
            }
        )
    metrics_v2 = classification_metrics(y_true, y_v2)
    metrics_v3 = classification_metrics(y_true, y_v31)
    dummy_full = classification_metrics(y_true, y_true)
    dummy_full_note = {
        **dummy_full,
        "note": "FULL not scored in feature-csv dry-run; placeholder is identity and MUST NOT be used as holdout FULL",
        "valid_for_formal_holdout": False,
    }
    verdict = adjudicate(
        metrics_full=dummy_full_note,
        metrics_v2=metrics_v2,
        metrics_v3_1=metrics_v3,
        per_sample_rows=[
            {
                **row,
                "full_prediction": row["ground_truth"],
            }
            for row in per
        ],
    )
    verdict["overall"] = "DRY_RUN_FEATURES_NOT_HOLDOUT"
    verdict["manual_review_flags"]["collapse_vs_FULL"]["status"] = "NOT_APPLICABLE_FEATURE_CSV_DRY_RUN"
    _write_consumed_lock(
        out_dir,
        {
            "status": "DRY_RUN_COMPLETE",
            "holdout_status": "NOT_HOLDOUT",
            "manifest_hash": None,
            "candidate_commit": CANDIDATE_COMMIT,
            "adjudicator_commit": _adjudicator_commit(),
            "run_id": out_dir.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "feature-csv dry-run; fresh holdout not used",
        },
    )
    _persist_common(
        out_dir,
        mode="DRY_RUN_FEATURES",
        holdout_manifest=None,
        per=per,
        metrics_full=_metrics_payload("FULL", dummy_full_note, float("nan"), "not_scored"),
        metrics_v2=_metrics_payload(
            "V2", metrics_v2, v2_thr, "fused_scratch_probability_effnet_plus_detector"
        ),
        metrics_v3=_metrics_payload(
            "V3-1", metrics_v3, V3_1_THRESHOLD, "logistic_replace_score_on_frozen_v2_features"
        ),
        verdict=verdict,
        holdout_status="NOT_HOLDOUT",
        extra_provenance={"feature_csv": str(feature_csv), "split": split},
    )
    return verdict


def run_formal(
    *,
    holdout_manifest: Path,
    out_dir: Path,
    device: str | None = None,
) -> dict:
    _assert_no_training_imports()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path = out_dir / "evaluation_lock.json"
    if lock_path.is_file():
        raise RuntimeError("REFUSE: evaluation_lock.json already exists for this run directory")

    manifest = json.loads(Path(holdout_manifest).read_text(encoding="utf-8"))
    images_dir = Path(manifest["images_dir"])
    started = datetime.now(timezone.utc).isoformat()
    consumed = {
        "status": "CONSUMED",
        "holdout_status": "CONSUMED",
        "manifest_hash": manifest.get("dataset_sha256"),
        "candidate_commit": CANDIDATE_COMMIT,
        "adjudicator_commit": _adjudicator_commit(),
        "run_id": out_dir.name,
        "timestamp": started,
        "reason": "formal scoring started",
    }
    _write_consumed_lock(out_dir, consumed)

    import cv2
    from gp.capability_v2 import FULL_INFERENCE_CONFIG, V2_INFERENCE_CONFIG, validate_frozen_artifacts
    from gp.scratch_v5 import ScratchV5Runtime

    validate_frozen_artifacts()
    v2_thr = load_v2_threshold()
    full_thr = load_full_threshold()
    veto = load_frozen_veto()
    runtime_full = ScratchV5Runtime(FULL_INFERENCE_CONFIG, device=device, warmup=True)
    runtime_v2 = ScratchV5Runtime(V2_INFERENCE_CONFIG, device=device, warmup=True)
    if abs(float(runtime_v2.default_threshold) - v2_thr) > 1e-12:
        raise RuntimeError("V2 runtime threshold != freeze artifact threshold")
    if abs(float(runtime_full.default_threshold) - full_thr) > 1e-12:
        raise RuntimeError("FULL runtime threshold != inference_config default_threshold")

    y_true, y_full, y_v2, y_v31 = [], [], [], []
    per = []
    try:
        for row in manifest["images"]:
            path = images_dir / row["file"]
            crop = cv2.imread(str(path))
            if crop is None:
                raise RuntimeError(f"failed to read {path}")
            label = 1 if row["label"] == "scratch" else 0
            full = score_full(runtime_full, crop, threshold=full_thr)
            v2 = score_v2(runtime_v2, crop, threshold=v2_thr)
            v31 = score_v3_1(runtime_v2, crop, veto, v2_threshold=v2_thr)
            y_true.append(label)
            y_full.append(int(full["prediction"]))
            y_v2.append(int(v2["prediction"]))
            y_v31.append(int(v31["prediction"]))
            per.append(
                {
                    "sample_id": row["file"],
                    "ground_truth": label,
                    "full_score": full["score"],
                    "full_prediction": full["prediction"],
                    "v2_score": v2["score"],
                    "v2_prediction": v2["prediction"],
                    "v3_1_score": v31["score"],
                    "v3_1_prediction": v31["prediction"],
                    "veto_probability": v31["veto_probability"],
                    "veto_triggered": v31["veto_triggered"],
                }
            )
    except Exception:
        consumed["reason"] = "runtime error after meaningful exposure"
        consumed["error"] = traceback.format_exc()
        consumed["status"] = "CONSUMED"
        _write_consumed_lock(out_dir, consumed)
        raise

    metrics_full = classification_metrics(y_true, y_full)
    metrics_v2 = classification_metrics(y_true, y_v2)
    metrics_v3 = classification_metrics(y_true, y_v31)
    verdict = adjudicate(
        metrics_full=metrics_full,
        metrics_v2=metrics_v2,
        metrics_v3_1=metrics_v3,
        per_sample_rows=per,
    )
    verdict["candidate_commit"] = CANDIDATE_COMMIT
    verdict["adjudicator_commit"] = consumed["adjudicator_commit"]
    verdict["holdout_status"] = "CONSUMED"
    _persist_common(
        out_dir,
        mode="FORMAL",
        holdout_manifest=manifest,
        per=per,
        metrics_full=_metrics_payload(
            "FULL",
            metrics_full,
            full_thr,
            "fused_scratch_probability_two_classifier_plus_detector",
        ),
        metrics_v2=_metrics_payload(
            "V2", metrics_v2, v2_thr, "fused_scratch_probability_effnet_plus_detector"
        ),
        metrics_v3=_metrics_payload(
            "V3-1", metrics_v3, V3_1_THRESHOLD, "logistic_replace_score_on_frozen_v2_features"
        ),
        verdict=verdict,
        holdout_status="CONSUMED",
        extra_provenance={},
    )
    consumed["reason"] = "formal adjudication completed"
    consumed["overall"] = verdict["overall"]
    _write_consumed_lock(out_dir, consumed)
    return verdict


def _persist_common(
    out_dir: Path,
    *,
    mode: str,
    holdout_manifest: dict | None,
    per: list[dict],
    metrics_full: dict,
    metrics_v2: dict,
    metrics_v3: dict,
    verdict: dict,
    holdout_status: str,
    extra_provenance: dict,
) -> None:
    try:
        git_status = _git(["status", "--short"])
        git_head = _git(["rev-parse", "HEAD"])
        git_branch = _git(["branch", "--show-current"])
    except (OSError, subprocess.CalledProcessError):
        git_status, git_head, git_branch = "", "UNKNOWN", "UNKNOWN"

    from gp.capability_v2 import load_frozen, validate_frozen_artifacts

    identity = validate_frozen_artifacts()
    veto = load_frozen_veto()
    veto_path = ROOT / "docs/capability-extraction/v3/v3-1-fp-veto/primary_veto_model.json"
    provenance = {
        "mode": mode,
        "candidate_commit": CANDIDATE_COMMIT,
        "adjudicator_commit": git_head,
        "branch": git_branch,
        "git_status": git_status,
        "v2_config_hash": identity["config_hash"],
        "classifier_sha": identity["classifier_sha"],
        "detector_sha": identity["detector_sha"],
        "v2_threshold": identity["threshold"],
        "v2_freeze_threshold": load_frozen()["threshold"],
        "full_threshold": load_full_threshold(),
        "veto_artifact": str(veto_path),
        "veto_artifact_sha256": _sha256_file(veto_path),
        "v3_1_threshold": V3_1_THRESHOLD,
        "fusion_mode": V3_1_MODE,
        "holdout_manifest_hash": None if holdout_manifest is None else holdout_manifest.get("dataset_sha256"),
        "holdout_status": holdout_status,
        "python": sys.version,
        "platform": sys.platform,
        **extra_provenance,
    }
    _write_json(out_dir / "provenance.json", provenance)
    if holdout_manifest is not None:
        _write_json(out_dir / "holdout_manifest.json", holdout_manifest)
        (out_dir / "holdout_manifest.sha256").write_text(
            str(holdout_manifest.get("dataset_sha256") or "") + "\n", encoding="utf-8"
        )
    fields = [
        "sample_id",
        "ground_truth",
        "full_score",
        "full_prediction",
        "v2_score",
        "v2_prediction",
        "v3_1_score",
        "v3_1_prediction",
        "veto_probability",
        "veto_triggered",
    ]
    with (out_dir / "per_sample_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in per:
            writer.writerow({key: row.get(key, "") for key in fields})
    _write_json(out_dir / "metrics_full.json", metrics_full)
    _write_json(out_dir / "metrics_v2.json", metrics_v2)
    _write_json(out_dir / "metrics_v3_1.json", metrics_v3)
    comparison = {
        "Q_D": {
            "FULL": metrics_full.get("Q_D"),
            "V2": metrics_v2.get("Q_D"),
            "V3-1": metrics_v3.get("Q_D"),
        },
        "FPR": {
            "FULL": metrics_full.get("fpr"),
            "V2": metrics_v2.get("fpr"),
            "V3-1": metrics_v3.get("fpr"),
        },
        "Recall": {
            "FULL": metrics_full.get("recall"),
            "V2": metrics_v2.get("recall"),
            "V3-1": metrics_v3.get("recall"),
        },
        "absolute_delta_v3_1_minus_v2": {
            "Q_D": float(metrics_v3["Q_D"]) - float(metrics_v2["Q_D"]),
            "FPR": float(metrics_v3["fpr"]) - float(metrics_v2["fpr"]),
            "Recall": float(metrics_v3["recall"]) - float(metrics_v2["recall"]),
        },
    }
    _write_json(out_dir / "comparison.json", comparison)
    verdict["candidate_commit"] = CANDIDATE_COMMIT
    verdict["adjudicator_commit"] = git_head
    verdict["holdout_status"] = holdout_status
    _write_json(out_dir / "adjudication.json", verdict)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V3-1 formal fresh-holdout adjudicator")
    parser.add_argument("--holdout-manifest", type=Path)
    parser.add_argument("--feature-csv", type=Path, help="val/synthetic dry-run only; not holdout")
    parser.add_argument("--split", default="val_scratch")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)
    if args.holdout_manifest and args.feature_csv:
        raise SystemExit("use either --holdout-manifest or --feature-csv")
    if args.feature_csv:
        run_from_feature_csv(feature_csv=args.feature_csv, out_dir=args.out_dir, split=args.split)
        return 0
    if not args.holdout_manifest:
        raise SystemExit("--holdout-manifest required for formal run")
    run_formal(holdout_manifest=args.holdout_manifest, out_dir=args.out_dir, device=args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
