"""Production-only Missing Hole V1 model bundle runtime."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from .scratch_v5 import apply_temperature, square_rgb_image


Box = Tuple[int, int, int, int]


@dataclass(frozen=True)
class MissingHolePrediction:
    probability: float
    classifier_probability: float
    detector_probability: float
    auxiliary_box: Optional[Box] = None
    classifier1_latency_ms: float = 0.0
    classifier2_latency_ms: float = 0.0
    detector_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0


def fuse_probabilities(first, second, detector, alpha=0.5):
    classifier_probability = (float(first) + float(second)) / 2.0
    fused = float(alpha) * classifier_probability + (1.0 - float(alpha)) * float(detector)
    if not math.isfinite(fused):
        raise RuntimeError("Missing Hole V1 输出包含 NaN 或 Inf")
    return fused, classifier_probability


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_missing_hole_config(path, verify_hashes=True):
    """Load, validate and resolve the Missing Hole V1 bundle configuration."""
    path = Path(path).expanduser().resolve()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到 Missing Hole 配置：{path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Missing Hole 配置不是有效 JSON：{path}: {exc}") from exc

    if config.get("version") != "missing_hole_v1":
        raise ValueError("Missing Hole 配置 version 必须为 missing_hole_v1")
    models = config.get("models")
    if not isinstance(models, list) or len(models) != 3:
        raise ValueError("Missing Hole V1 必须配置两个分类器和一个检测器")
    classifiers = [item for item in models if item.get("kind") == "classifier"]
    detectors = [item for item in models if item.get("kind") == "detector"]
    if len(classifiers) != 2 or len(detectors) != 1:
        raise ValueError("Missing Hole V1 模型种类配置无效")

    fusion = config.get("fusion", {})
    if fusion.get("type") != "weighted" or fusion.get("classifier", {}).get("type") != "classifier_mean":
        raise ValueError("Missing Hole V1 仅支持 weighted + classifier_mean 融合")
    names = [str(item.get("name", "")) for item in classifiers]
    detector_name = str(detectors[0].get("name", ""))
    if len(set(names)) != 2 or set(fusion["classifier"].get("models", [])) != set(names):
        raise ValueError("Missing Hole 分类器名称与融合配置不一致")
    if fusion.get("detector") != detector_name:
        raise ValueError("Missing Hole 检测器名称与融合配置不一致")

    threshold = float(config.get("default_threshold", -1.0))
    alpha = float(fusion.get("alpha", -1.0))
    if not 0.0 < threshold < 1.0 or not 0.0 <= alpha <= 1.0:
        raise ValueError("Missing Hole 阈值或融合权重超出范围")
    for item in classifiers:
        if item.get("family") not in {"efficientnet_b0", "resnet18"}:
            raise ValueError(f"不支持的 Missing Hole 分类器：{item.get('family')}")
        if int(item.get("imgsz", 0)) < 1 or float(item.get("temperature", 0.0)) <= 0.0:
            raise ValueError(f"Missing Hole 分类器尺寸或温度无效：{item.get('name')}")
        if item.get("tta", "none") != "none":
            raise ValueError("当前 Missing Hole 运行时仅支持 tta=none")
    detector = detectors[0]
    if detector.get("scheme") != "one_class" or detector.get("family") != "standard":
        raise ValueError("Missing Hole 检测器必须为 standard 单类模型")
    if int(detector.get("imgsz", 0)) < 1 or float(detector.get("temperature", 0.0)) <= 0.0:
        raise ValueError("Missing Hole 检测器尺寸或温度无效")
    if not 0.0 < float(detector.get("conf_floor", -1.0)) < 1.0:
        raise ValueError("Missing Hole detector conf_floor 超出范围")
    if not 0.0 < float(detector.get("iou", -1.0)) <= 1.0:
        raise ValueError("Missing Hole detector iou 超出范围")

    for item in models:
        weight = Path(str(item.get("weights", "")))
        if not weight.is_absolute():
            weight = path.parent / weight
        weight = weight.resolve()
        if not weight.is_file():
            raise FileNotFoundError(f"找不到 Missing Hole 权重：{weight}")
        expected = str(item.get("sha256", "")).lower()
        if verify_hashes and (not expected or _sha256(weight) != expected):
            raise ValueError(f"Missing Hole 权重校验失败：{weight.name}")
        item["weights"] = weight
    config["config_path"] = path
    return config


class MissingHoleRuntime:
    """Load the two classifiers and detector once per inspection worker."""

    def __init__(self, config_path, device=None, warmup=True):
        import torch
        from torchvision import transforms
        from ultralytics import YOLO

        self.config = load_missing_hole_config(config_path)
        self.version = self.config["version"]
        self.torch = torch
        self.device = torch.device(device or ("cuda:0" if torch.cuda.is_available() else "cpu"))
        self.yolo_device = 0 if self.device.type == "cuda" else "cpu"
        self.tensor_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        models = self.config["models"]
        self.classifiers = [self._load_classifier(item) for item in models if item["kind"] == "classifier"]
        self.detector_config = next(item for item in models if item["kind"] == "detector")
        self.detector = YOLO(str(self.detector_config["weights"]), task="detect")
        if set(self.detector.names.values()) != {"missing_hole"}:
            raise ValueError("Missing Hole detector 必须是单类别 missing_hole 模型")
        if warmup:
            self._warmup()

    @property
    def default_threshold(self):
        return float(self.config["default_threshold"])

    def _load_classifier(self, item):
        from torchvision.models import efficientnet_b0, resnet18

        try:
            checkpoint = self.torch.load(str(item["weights"]), map_location="cpu", weights_only=True)
        except TypeError:
            checkpoint = self.torch.load(str(item["weights"]), map_location="cpu")
        state_dict = checkpoint.get("model", checkpoint)
        family = str(item["family"])
        if family == "efficientnet_b0":
            model = efficientnet_b0(weights=None)
            outputs = int(state_dict["classifier.1.weight"].shape[0])
            model.classifier[1] = self.torch.nn.Linear(model.classifier[1].in_features, outputs)
        else:
            model = resnet18(weights=None)
            outputs = int(state_dict["fc.weight"].shape[0])
            model.fc = self.torch.nn.Linear(model.fc.in_features, outputs)
        if outputs != 1:
            raise ValueError(f"Missing Hole 分类器必须只有一个输出：{item['name']}")
        model.load_state_dict(state_dict)
        model.to(self.device).eval()
        return item, model

    def _warmup(self):
        with self.torch.inference_mode():
            for item, model in self.classifiers:
                size = int(item["imgsz"])
                model(self.torch.zeros((1, 3, size, size), device=self.device))
        size = int(self.detector_config["imgsz"])
        self.detector.predict(
            np.zeros((size, size, 3), dtype=np.uint8),
            imgsz=size,
            conf=float(self.detector_config["conf_floor"]),
            iou=float(self.detector_config["iou"]),
            device=self.yolo_device,
            verbose=False,
        )

    def predict(self, crop):
        if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
            raise ValueError("Missing Hole V1 收到空齿轮 ROI")
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        classifier_scores = []
        classifier_times = []
        with self.torch.inference_mode():
            for item, model in self.classifiers:
                started = time.perf_counter()
                image = square_rgb_image(rgb, int(item["imgsz"]))
                tensor = self.tensor_transform(image).unsqueeze(0).to(self.device)
                raw = float(model(tensor).sigmoid()[0, 0].item())
                classifier_times.append((time.perf_counter() - started) * 1000)
                classifier_scores.append(apply_temperature(raw, item["temperature"]))

        started = time.perf_counter()
        result = self.detector.predict(
            crop,
            imgsz=int(self.detector_config["imgsz"]),
            conf=float(self.detector_config["conf_floor"]),
            iou=float(self.detector_config["iou"]),
            device=self.yolo_device,
            verbose=False,
        )[0]
        detector_ms = (time.perf_counter() - started) * 1000
        raw_detector = 0.0
        auxiliary_box = None
        if result.boxes is not None and len(result.boxes):
            confidences = result.boxes.conf.detach().cpu().numpy()
            best_index = int(np.argmax(confidences))
            raw_detector = float(confidences[best_index])
            if raw_detector >= float(self.detector_config.get("display_confidence", 0.05)):
                coordinates = result.boxes.xyxy[best_index].detach().cpu().tolist()
                auxiliary_box = _clip_box(coordinates, crop.shape)

        started = time.perf_counter()
        detector_score = apply_temperature(raw_detector, self.detector_config["temperature"])
        fused, classifier_score = fuse_probabilities(
            classifier_scores[0], classifier_scores[1], detector_score, self.config["fusion"]["alpha"]
        )
        fusion_ms = (time.perf_counter() - started) * 1000
        if not all(math.isfinite(value) for value in (fused, classifier_score, detector_score)):
            raise RuntimeError("Missing Hole V1 输出包含 NaN 或 Inf")
        return MissingHolePrediction(
            fused,
            classifier_score,
            detector_score,
            auxiliary_box,
            classifier_times[0],
            classifier_times[1],
            detector_ms,
            fusion_ms,
        )


def _clip_box(box, shape):
    height, width = shape[:2]
    x1, y1, x2, y2 = (int(round(value)) for value in box)
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)
