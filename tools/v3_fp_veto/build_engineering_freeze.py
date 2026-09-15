#!/usr/bin/env python3
"""Build V3-1 engineering freeze package (no param changes).

Locks the candidate at exploration commit 2377521.
Does NOT touch fresh holdout or production registry.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREEZE_DIR = ROOT / "docs" / "capability-extraction" / "v3" / "v3-1-engineering-freeze"
VETO_DIR = ROOT / "docs" / "capability-extraction" / "v3" / "v3-1-fp-veto"
EXPLORATION_COMMIT = "2377521f827ba8137025c6bb53afe590db1bd982"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def split_manifest(images: Path, annotations: Path, split: str) -> dict:
    paths = sorted(p for p in images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    rows = []
    for path in paths:
        xml = annotations / f"{path.stem}.xml"
        label = 1 if xml.is_file() else 0
        rows.append({"image": path.name, "label": label, "sha256": sha256_file(path)})
    blob = "\n".join(f"{r['image']},{r['label']},{r['sha256']}" for r in rows) + "\n"
    return {
        "split": split,
        "n": len(rows),
        "positives": sum(r["label"] for r in rows),
        "manifest_sha256": sha256_text(blob),
        "rows": rows,
    }


def main():
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    from gp.capability_v2 import FROZEN_PATH, V2_INFERENCE_CONFIG, load_frozen, validate_frozen_artifacts

    frozen_v2 = load_frozen()
    validate_frozen_artifacts(frozen_v2)

    veto_model = VETO_DIR / "primary_veto_model.json"
    features = VETO_DIR / "features_train_val.csv"
    pareto = VETO_DIR / "pareto_report.json"
    extract_py = ROOT / "tools" / "v3_fp_veto" / "extract_features.py"
    train_py = ROOT / "tools" / "v3_fp_veto" / "train_pareto.py"
    cls1 = ROOT / "model" / "model2" / "classifier_1.pt"
    det = ROOT / "model" / "model2" / "detector.pt"

    # Prefer dataset_audit paths if present
    img_root = Path(r"G:/CODE/Machine_vision_dataset_audit/dataset_defects/images")
    ann_root = Path(r"G:/CODE/Machine_vision_dataset_audit/dataset_defects/annotations")
    if not (img_root / "train_scratch").is_dir():
        img_root = Path("/home/jetson/Projects/Machine_vision_dataset/dataset_defects/images")
        ann_root = Path("/home/jetson/Projects/Machine_vision_dataset/dataset_defects/annotations")

    train_m = split_manifest(img_root / "train_scratch", ann_root / "train_scratch", "train_scratch")
    val_m = split_manifest(img_root / "val_scratch", ann_root / "val_scratch", "val_scratch")
    # drop full rows from freeze json to keep size manageable — store separately
    train_rows = train_m.pop("rows")
    val_rows = val_m.pop("rows")
    (FREEZE_DIR / "manifest_train_scratch.csv").write_text(
        "image,label,sha256\n" + "\n".join(f"{r['image']},{r['label']},{r['sha256']}" for r in train_rows) + "\n",
        encoding="utf-8",
    )
    (FREEZE_DIR / "manifest_val_scratch.csv").write_text(
        "image,label,sha256\n" + "\n".join(f"{r['image']},{r['label']},{r['sha256']}" for r in val_rows) + "\n",
        encoding="utf-8",
    )

    pareto_payload = json.loads(pareto.read_text(encoding="utf-8"))
    veto_payload = json.loads(veto_model.read_text(encoding="utf-8"))

    package = {
        "candidate_id": "scratch_v3_1_fp_veto_logistic",
        "status": "V3-1 CANDIDATE PROMISING — ENGINEERING FREEZE",
        "freeze_utc": datetime.now(timezone.utc).isoformat(),
        "exploration_commit": EXPLORATION_COMMIT,
        "freeze_commit_at_build": git_head(),
        "branch": "experiment/v3-lightweight-fp-veto",
        "fresh_holdout": "UNTOUCHED",
        "registry": "UNCHANGED",
        "param_lock": (
            "From this freeze forward, V3-1 parameters must not change "
            "before fresh-holdout adjudication."
        ),
        "backbone": {
            "profile": "LATENCY_DEGRADED_V2",
            "frozen_v2_path": str(FROZEN_PATH.relative_to(ROOT)).replace("\\", "/"),
            "frozen_v2_config_hash": frozen_v2["config_hash"],
            "inference_config": str(V2_INFERENCE_CONFIG.relative_to(ROOT)).replace("\\", "/"),
            "classifier_1_pt": "model/model2/classifier_1.pt",
            "classifier_1_sha256": sha256_file(cls1),
            "detector_pt": "model/model2/detector.pt",
            "detector_sha256": sha256_file(det),
            "expected_classifier_sha256": frozen_v2["classifier"]["sha256"],
            "expected_detector_sha256": frozen_v2["detector"]["sha256"],
            "v2_threshold": frozen_v2["threshold"],
            "fusion_alpha": frozen_v2["fusion"]["alpha"],
        },
        "veto": {
            "type": veto_payload["type"],
            "mode": veto_payload["mode"],
            "threshold": veto_payload["threshold"],
            "feature_names": veto_payload["feature_names"],
            "artifact": "docs/capability-extraction/v3/v3-1-fp-veto/primary_veto_model.json",
            "artifact_sha256": sha256_file(veto_model),
            "canonical_payload_sha256": sha256_text(
                json.dumps(veto_payload, sort_keys=True, separators=(",", ":"))
            ),
        },
        "feature_extraction": {
            "implementation": "tools/v3_fp_veto/extract_features.py",
            "implementation_sha256": sha256_file(extract_py),
            "train_script": "tools/v3_fp_veto/train_pareto.py",
            "train_script_sha256": sha256_file(train_py),
            "features_csv": "docs/capability-extraction/v3/v3-1-fp-veto/features_train_val.csv",
            "features_csv_sha256": sha256_file(features),
        },
        "dataset": {
            "source": "Machine_vision_dataset / dataset_defects",
            "annotation_format": "Pascal VOC XML; presence of scratch object => positive",
            "label_rule": "XML with >=1 object => 1 else 0",
            "splits_used": ["train_scratch", "val_scratch"],
            "splits_forbidden": ["test_scratch", "fresh_holdout"],
            "train_manifest": train_m,
            "val_manifest": val_m,
            "manifest_train_csv_sha256": sha256_file(FREEZE_DIR / "manifest_train_scratch.csv"),
            "manifest_val_csv_sha256": sha256_file(FREEZE_DIR / "manifest_val_scratch.csv"),
        },
        "training": {
            "seed": {"logistic_l2_1e-2": 0},
            "command": (
                "python -u tools/v3_fp_veto/extract_features.py "
                "--splits train_scratch val_scratch && "
                "python -u tools/v3_fp_veto/train_pareto.py"
            ),
            "selection": "max val Q_D among candidates; threshold swept on val only",
            "python": sys.version,
            "platform": platform.platform(),
        },
        "metrics_at_freeze": {
            "v2_val": pareto_payload["baselines"]["v2_val"],
            "v2_train": pareto_payload["baselines"]["v2_train"],
            "v3_1_val": pareto_payload["selection"]["primary"]["val_best"],
            "v3_1_train_at_val_threshold": pareto_payload["selection"]["primary"]["train_at_val_threshold"],
            "delta_qd_vs_v2_val": pareto_payload["selection"]["delta_qd_vs_v2"],
            "delta_fpr_vs_v2_val": pareto_payload["selection"]["delta_fpr_vs_v2"],
            "note": (
                "Recall dropped 0.977→0.930 on val (FN↔FP trade). "
                "Q_D improved; confirmatory judgment deferred to preregistered fresh holdout."
            ),
        },
        "latency_component": {
            "veto_overhead_json": "docs/capability-extraction/v3/v3-1-fp-veto/veto_overhead.json",
            "veto_overhead_sha256": sha256_file(VETO_DIR / "veto_overhead.json")
            if (VETO_DIR / "veto_overhead.json").is_file()
            else None,
            "note": "component microbench only; NX S1 integrated paired required",
        },
        "hard_constraints": {
            "s1_integrated_p95_ms_max": 190.0,
            "s1_extra_budget_vs_v2_ms": 12.0,
            "no_second_backbone": True,
        },
    }

    # Integrity hash of freeze package body without self hash
    package["freeze_package_hash"] = ""
    package["freeze_package_hash"] = sha256_text(
        json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )

    json_path = FREEZE_DIR / "v3-1-engineering-freeze.json"
    json_path.write_text(json.dumps(package, indent=2), encoding="utf-8")

    md = f"""# V3-1 Engineering Freeze

```text
status: V3-1 CANDIDATE PROMISING — ENGINEERING FREEZE
exploration_commit: {EXPLORATION_COMMIT}
fresh_holdout: UNTOUCHED
registry: UNCHANGED
param_lock: NO CHANGES until after fresh-holdout adjudication
```

## Identity

| item | value |
| --- | --- |
| candidate_id | `scratch_v3_1_fp_veto_logistic` |
| freeze_package_hash | `{package['freeze_package_hash']}` |
| V2 config_hash | `{frozen_v2['config_hash']}` |
| classifier_1 SHA | `{package['backbone']['classifier_1_sha256']}` |
| detector SHA | `{package['backbone']['detector_sha256']}` |
| veto artifact SHA | `{package['veto']['artifact_sha256']}` |
| mode | `replace_score` |
| veto threshold | `{veto_payload['threshold']}` |
| train manifest SHA | `{train_m['manifest_sha256']}` |
| val manifest SHA | `{val_m['manifest_sha256']}` |

## Metrics at freeze (val)

| | V2 | V3-1 |
| --- | ---: | ---: |
| Q_D | {pareto_payload['baselines']['v2_val']['Q_D']:.4f} | {pareto_payload['selection']['primary']['val_best']['Q_D']:.4f} |
| FPR | {pareto_payload['baselines']['v2_val']['fpr']:.4f} | {pareto_payload['selection']['primary']['val_best']['fpr']:.4f} |
| Recall | {pareto_payload['baselines']['v2_val']['recall']:.4f} | {pareto_payload['selection']['primary']['val_best']['recall']:.4f} |

Recall cost on val is acknowledged (FN↔FP). Not validated until preregistered fresh holdout.

## Reproduce

See `v3-1-engineering-freeze.json` + manifests in this directory.
Feature extract + train scripts hashed in the JSON; do not retune.

## Next gate

NX S1 paired V2 vs V3-1 integrated latency (`delta_p95`), then stop for holdout preregistration adjudication.
"""
    (FREEZE_DIR / "v3-1-engineering-freeze.md").write_text(md, encoding="utf-8")
    print(json.dumps({"wrote": str(json_path), "hash": package["freeze_package_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
