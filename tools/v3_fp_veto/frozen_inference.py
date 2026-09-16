"""Frozen FULL / V2 / V3-1 inference primitives for V3-1 formal evaluation.

Source of truth for V3-1 apply is the NX S1 path:
frozen feature_names order → frozen mean/std → frozen logistic → threshold 0.845
→ replace_score.

Does not import train_pareto.py. Does not fit, sweep, or select.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CANDIDATE_COMMIT = "e8b2b0fda2af2c9c8c697d4655d527947381377a"
V3_1_THRESHOLD = 0.845
V3_1_MODE = "replace_score"
EXPECTED_FEATURE_NAMES = [
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
DEFAULT_VETO_ARTIFACT = Path("docs/capability-extraction/v3/v3-1-fp-veto/primary_veto_model.json")
V2_FROZEN_PATH = Path("docs/capability-extraction/v3/latency_degraded_v2_effnet_det.frozen.json")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class FrozenVeto:
    payload: dict
    mean: np.ndarray
    std: np.ndarray
    weights: np.ndarray
    bias: float
    feature_names: tuple[str, ...]
    threshold: float
    mode: str

    def vector(self, feat: dict) -> np.ndarray:
        return np.asarray([float(feat[name]) for name in self.feature_names], dtype=np.float64)

    def normalized(self, feat: dict) -> np.ndarray:
        return (self.vector(feat) - self.mean) / self.std

    def predict_proba(self, feat: dict) -> float:
        xs = self.normalized(feat)
        z = float(xs @ self.weights + self.bias)
        z = min(max(z, -30.0), 30.0)
        return 1.0 / (1.0 + math.exp(-z))

    def replace_score(self, feat: dict) -> tuple[float, int]:
        """Mode A freeze semantics: logistic probability *replaces* V2 fused score.

        Prediction is ``p >= 0.845``. This is not Mode B
        (``v2_reject AND p >= thr``). The frozen candidate is replace_score.
        """
        proba = self.predict_proba(feat)
        return proba, int(proba >= self.threshold)


def load_veto(path: Path | None = None) -> tuple[dict, callable, float, list[str]]:
    """NX S1 compatible loader: payload, proba(feat), threshold, names."""
    model = load_frozen_veto(path)
    return model.payload, model.predict_proba, model.threshold, list(model.feature_names)


def load_frozen_veto(path: Path | None = None) -> FrozenVeto:
    root = _project_root()
    artifact = Path(path) if path is not None else root / DEFAULT_VETO_ARTIFACT
    if not artifact.is_absolute():
        artifact = root / artifact
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    names = list(payload["feature_names"])
    if names != EXPECTED_FEATURE_NAMES:
        raise ValueError(f"frozen feature_names order mismatch: {names}")
    if str(payload.get("mode")) != V3_1_MODE:
        raise ValueError(f"frozen mode mismatch: {payload.get('mode')}")
    threshold = float(payload["threshold"])
    if abs(threshold - V3_1_THRESHOLD) > 1e-12:
        raise ValueError(f"frozen threshold mismatch: {threshold}")
    if str(payload.get("type")) != "logistic":
        raise ValueError(f"frozen veto type mismatch: {payload.get('type')}")
    return FrozenVeto(
        payload=payload,
        mean=np.asarray(payload["mean"], dtype=np.float64),
        std=np.asarray(payload["std"], dtype=np.float64),
        weights=np.asarray(payload["weights"], dtype=np.float64),
        bias=float(payload["bias"]),
        feature_names=tuple(names),
        threshold=threshold,
        mode=str(payload["mode"]),
    )


def load_v2_threshold(frozen_path: Path | None = None) -> float:
    """V2 operating threshold from the V2 freeze artifact, not a generic script default."""
    from gp.capability_v2 import load_frozen

    payload = load_frozen(frozen_path)
    threshold = float(payload["threshold"])
    listed_path = payload.get("runtime_inference_config")
    if listed_path:
        cfg_path = _project_root() / listed_path
        runtime_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        runtime_thr = float(runtime_cfg["default_threshold"])
        if abs(runtime_thr - threshold) > 1e-12:
            raise ValueError(
                f"V2 threshold drift: freeze={threshold} inference_config={runtime_thr}"
            )
    return threshold


def load_full_threshold() -> float:
    from gp.capability_v2 import FULL_INFERENCE_CONFIG

    runtime_cfg = json.loads(Path(FULL_INFERENCE_CONFIG).read_text(encoding="utf-8"))
    return float(runtime_cfg["default_threshold"])


def backbone_features(runtime, crop):
    """NX S1 V3-1 feature extraction on an already-loaded V2 ScratchV5Runtime."""
    from gp.scratch_v5 import apply_temperature, fuse_single_classifier, square_rgb_image
    import cv2

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    item, model = runtime.classifiers[0]
    with runtime.torch.inference_mode():
        tensor = runtime.tensor_transform(square_rgb_image(rgb, int(item["imgsz"]))).unsqueeze(0).to(
            runtime.device
        )
        raw_cls = float(model(tensor).sigmoid()[0, 0].item())
    cls1 = apply_temperature(raw_cls, item.get("temperature", 1.0))
    detector = runtime.config["detector"]
    result = runtime.detector.predict(
        crop,
        imgsz=int(detector["imgsz"]),
        conf=float(detector["conf_floor"]),
        iou=float(detector["iou"]),
        device=runtime.yolo_device,
        verbose=False,
    )[0]
    raw_confs = []
    if result.boxes is not None and len(result.boxes):
        raw_confs = [float(c) for c in result.boxes.conf.detach().cpu().numpy().tolist()]
    raw_det = max(raw_confs) if raw_confs else 0.0
    det = apply_temperature(raw_det, detector.get("temperature", 1.0))
    alpha = float(runtime.config["fusion"]["alpha"])
    fused, _ = fuse_single_classifier(cls1, det, alpha)
    n_boxes = len(raw_confs)
    top3 = sorted(raw_confs, reverse=True)[:3]
    while len(top3) < 3:
        top3.append(0.0)
    return {
        "raw_cls": raw_cls,
        "cls1": cls1,
        "raw_det": raw_det,
        "det": det,
        "fused_v2": fused,
        "n_boxes": n_boxes,
        "sum_conf": float(sum(raw_confs)),
        "mean_conf": float(sum(raw_confs) / n_boxes) if n_boxes else 0.0,
        "top1_conf": top3[0],
        "top2_conf": top3[1],
        "top3_conf": top3[2],
        "cls_minus_det": cls1 - det,
        "log1p_boxes": math.log1p(n_boxes),
    }


def score_full(runtime, crop, threshold: float | None = None) -> dict:
    """FULL: ScratchV5Runtime.predict defect_score vs FULL default_threshold."""
    pred = runtime.predict(crop)
    thr = float(runtime.default_threshold if threshold is None else threshold)
    score = float(pred.defect_score)
    return {
        "arm": "FULL",
        "score": score,
        "prediction": int(score >= thr),
        "threshold": thr,
        "score_semantics": "fused_scratch_probability_two_classifier_plus_detector",
    }


def score_v2(runtime, crop, threshold: float | None = None) -> dict:
    """V2: ScratchV5Runtime.predict defect_score vs frozen V2 threshold."""
    pred = runtime.predict(crop)
    thr = float(runtime.default_threshold if threshold is None else threshold)
    score = float(pred.defect_score)
    return {
        "arm": "V2",
        "score": score,
        "prediction": int(score >= thr),
        "threshold": thr,
        "score_semantics": "fused_scratch_probability_effnet_plus_detector",
    }


def score_v3_1(runtime_v2, crop, veto: FrozenVeto, v2_threshold: float) -> dict:
    """V3-1: NX S1 frozen apply + replace_score. Uses V2 runtime for features only."""
    feat = backbone_features(runtime_v2, crop)
    proba, prediction = veto.replace_score(feat)
    v2_pred = int(float(feat["fused_v2"]) >= float(v2_threshold))
    return {
        "arm": "V3-1",
        "score": proba,
        "prediction": prediction,
        "threshold": veto.threshold,
        "score_semantics": "logistic_replace_score_on_frozen_v2_features",
        "veto_probability": proba,
        "veto_triggered": int(bool(v2_pred) and not bool(prediction)),
        "v2_fused": float(feat["fused_v2"]),
        "v2_prediction": v2_pred,
        "features": feat,
        "feature_vector": veto.vector(feat).tolist(),
        "normalized_vector": veto.normalized(feat).tolist(),
    }


def apply_veto_to_feature_row(row: dict, veto: FrozenVeto, v2_threshold: float | None = None) -> dict:
    """Apply frozen logistic to a precomputed feature row (val/synthetic only)."""
    feat = {name: float(row[name]) for name in veto.feature_names}
    proba, prediction = veto.replace_score(feat)
    if v2_threshold is None:
        v2_pred = int(row["v2_reject"]) if "v2_reject" in row else int(
            float(row["fused_v2"]) >= load_v2_threshold()
        )
    else:
        v2_pred = int(float(row["fused_v2"]) >= float(v2_threshold))
    return {
        "score": proba,
        "prediction": prediction,
        "veto_probability": proba,
        "veto_triggered": int(bool(v2_pred) and not bool(prediction)),
        "v2_prediction": v2_pred,
        "feature_vector": veto.vector(feat).tolist(),
        "normalized_vector": veto.normalized(feat).tolist(),
    }
