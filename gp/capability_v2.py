"""LATENCY_DEGRADED_V2 frozen capability helpers (fail-closed)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gp.config import PROJECT_ROOT

FROZEN_PATH = PROJECT_ROOT / "docs" / "capability-extraction" / "v3" / "latency_degraded_v2_effnet_det.frozen.json"
V2_INFERENCE_CONFIG = PROJECT_ROOT / "model" / "model2" / "profiles" / "latency_degraded_v2" / "inference_config.json"
FULL_INFERENCE_CONFIG = PROJECT_ROOT / "model" / "model2" / "inference_config.json"
PROFILE_ID = "LATENCY_DEGRADED_V2"

REASON_ARTIFACT_MISSING = "CAPABILITY_ARTIFACT_MISSING"
REASON_HASH_MISMATCH = "CAPABILITY_HASH_MISMATCH"
REASON_CONFIG_MISMATCH = "CAPABILITY_CONFIG_MISMATCH"
REASON_NOT_APPROVED = "CAPABILITY_NOT_APPROVED"
REASON_NOT_IMPLEMENTED = "CAPABILITY_NOT_IMPLEMENTED"


class CapabilityArtifactError(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_config_hash(payload: dict) -> str:
    data = dict(payload)
    data["config_hash"] = ""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_frozen(path: Path | None = None) -> dict:
    frozen_path = Path(path) if path is not None else FROZEN_PATH
    if not frozen_path.is_file():
        raise CapabilityArtifactError(REASON_ARTIFACT_MISSING, f"missing frozen artifact: {frozen_path}")
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CapabilityArtifactError(REASON_CONFIG_MISMATCH, "frozen artifact must be an object")
    expected = compute_config_hash(payload)
    listed = str(payload.get("config_hash") or "")
    if not listed or listed != expected:
        raise CapabilityArtifactError(
            REASON_HASH_MISMATCH,
            f"frozen config_hash mismatch: listed={listed} expected={expected}",
        )
    return payload


def validate_frozen_artifacts(frozen: dict | None = None) -> dict:
    """Verify weights SHA and inference config match the frozen candidate."""
    payload = frozen if frozen is not None else load_frozen()
    reasons = []
    classifier = payload["classifier"]
    detector = payload["detector"]
    cls_path = PROJECT_ROOT / classifier["weights_path"]
    det_path = PROJECT_ROOT / detector["weights_path"]
    if not cls_path.is_file():
        raise CapabilityArtifactError(REASON_ARTIFACT_MISSING, f"missing classifier: {cls_path}")
    if not det_path.is_file():
        raise CapabilityArtifactError(REASON_ARTIFACT_MISSING, f"missing detector: {det_path}")
    cls_sha = _sha256_file(cls_path)
    det_sha = _sha256_file(det_path)
    if cls_sha != str(classifier["sha256"]).lower():
        raise CapabilityArtifactError(
            REASON_HASH_MISMATCH,
            f"classifier SHA mismatch: {cls_sha} != {classifier['sha256']}",
        )
    if det_sha != str(detector["sha256"]).lower():
        raise CapabilityArtifactError(
            REASON_HASH_MISMATCH,
            f"detector SHA mismatch: {det_sha} != {detector['sha256']}",
        )
    if not V2_INFERENCE_CONFIG.is_file():
        raise CapabilityArtifactError(REASON_ARTIFACT_MISSING, f"missing V2 inference config: {V2_INFERENCE_CONFIG}")
    runtime_cfg = json.loads(V2_INFERENCE_CONFIG.read_text(encoding="utf-8"))
    if float(runtime_cfg.get("default_threshold")) != float(payload["threshold"]):
        reasons.append("threshold")
    if float(runtime_cfg.get("fusion", {}).get("alpha")) != float(payload["fusion"]["alpha"]):
        reasons.append("fusion.alpha")
    if runtime_cfg.get("fusion", {}).get("classifier", {}).get("type") != "classifier_single":
        reasons.append("fusion.classifier.type")
    if int(runtime_cfg["classifiers"][0]["imgsz"]) != int(classifier["input_size"]):
        reasons.append("classifier.imgsz")
    if int(runtime_cfg["detector"]["imgsz"]) != int(detector["input_size"]):
        reasons.append("detector.imgsz")
    if reasons:
        raise CapabilityArtifactError(
            REASON_CONFIG_MISMATCH,
            "runtime inference_config drift vs frozen: " + ",".join(reasons),
        )
    return {
        "profile_id": PROFILE_ID,
        "config_hash": payload["config_hash"],
        "classifier_sha": cls_sha,
        "detector_sha": det_sha,
        "threshold": float(payload["threshold"]),
        "classifier_input_size": int(classifier["input_size"]),
        "detector_input_size": int(detector["input_size"]),
        "fusion_alpha": float(payload["fusion"]["alpha"]),
        "inference_config": str(V2_INFERENCE_CONFIG),
        "applicability": list(payload.get("applicability") or []),
    }


def capability_identity_from_runtime(model2_config: Path, defect_threshold: float) -> dict:
    """Describe the active Scratch bundle without trusting profile string alone."""
    path = Path(model2_config)
    identity = {
        "model2_config": str(path),
        "model2_config_exists": path.is_file(),
        "defect_threshold": float(defect_threshold),
        "scratch_version": None,
        "classifier_count": None,
        "classifier_names": [],
        "classifier_shas": [],
        "detector_sha": None,
        "detector_imgsz": None,
        "fusion_type": None,
        "fusion_alpha": None,
        "matches_latency_degraded_v2": False,
        "matches_full_scratch_v5": False,
    }
    if not path.is_file():
        return identity
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return identity
    identity["scratch_version"] = cfg.get("version")
    classifiers = cfg.get("classifiers") or []
    identity["classifier_count"] = len(classifiers)
    identity["classifier_names"] = [str(item.get("name") or "") for item in classifiers]
    identity["classifier_shas"] = [str(item.get("sha256") or "").lower() for item in classifiers]
    detector = cfg.get("detector") or {}
    identity["detector_sha"] = str(detector.get("sha256") or "").lower()
    identity["detector_imgsz"] = detector.get("imgsz")
    fusion = cfg.get("fusion") or {}
    identity["fusion_type"] = (fusion.get("classifier") or {}).get("type")
    identity["fusion_alpha"] = fusion.get("alpha")
    identity["matches_full_scratch_v5"] = (
        cfg.get("version") == "scratch_v5" and len(classifiers) == 2
    )
    try:
        frozen = load_frozen()
        identity["matches_latency_degraded_v2"] = (
            cfg.get("version") == "scratch_v5_latency_degraded_v2"
            and len(classifiers) == 1
            and identity["classifier_shas"] == [frozen["classifier"]["sha256"]]
            and identity["detector_sha"] == frozen["detector"]["sha256"]
            and abs(float(cfg.get("default_threshold")) - float(frozen["threshold"])) < 1e-12
            and abs(float(fusion.get("alpha")) - float(frozen["fusion"]["alpha"])) < 1e-12
            and abs(float(defect_threshold) - float(frozen["threshold"])) < 1e-12
        )
    except CapabilityArtifactError:
        identity["matches_latency_degraded_v2"] = False
    return identity
