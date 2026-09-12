"""Production-only Scratch V5 model bundle runtime."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image


Box = Tuple[int, int, int, int]


@dataclass(frozen=True)
class ScratchV5Prediction:
    defect_score: float
    classifier_probability: float
    detector_probability: float
    auxiliary_box: Optional[Box] = None


def apply_temperature(probability, temperature):
    """Apply the probability calibration used during Scratch V5 selection."""
    probability = min(max(float(probability), 1e-6), 1.0 - 1e-6)
    logit = math.log(probability / (1.0 - probability))
    return 1.0 / (1.0 + math.exp(-logit / float(temperature)))


def fuse_probabilities(first, second, detector, alpha=0.25):
    classifier_probability = (float(first) + float(second)) / 2.0
    fused = float(alpha) * classifier_probability + (1.0 - float(alpha)) * float(detector)
    if not math.isfinite(fused):
        raise RuntimeError("Scratch V5 输出包含 NaN 或 Inf")
    return fused, classifier_probability


def square_rgb_image(image, size):
    """Resize without distortion and center on the V5 gray canvas."""
    if not isinstance(image, Image.Image):
        image = Image.fromarray(np.asarray(image, dtype=np.uint8), mode="RGB")
    image = image.convert("RGB")
    if image.width < 1 or image.height < 1:
        raise ValueError("Scratch V5 输入图像尺寸无效")
    scale = int(size) / max(image.size)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (int(size), int(size)), (238, 238, 238))
    canvas.paste(resized, ((int(size) - resized.width) // 2, (int(size) - resized.height) // 2))
    return canvas


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model2_config(path, verify_hashes=True):
    """Load, validate and resolve a Scratch V5 bundle configuration."""
    path = Path(path).expanduser().resolve()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到 Model2 配置：{path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model2 配置不是有效 JSON：{path}: {exc}") from exc

    if config.get("version") != "scratch_v5":
        raise ValueError("Model2 配置 version 必须为 scratch_v5")
    classifiers = config.get("classifiers")
    if not isinstance(classifiers, list) or len(classifiers) != 2:
        raise ValueError("Scratch V5 必须配置两个分类器")
    if not isinstance(config.get("detector"), dict):
        raise ValueError("Scratch V5 缺少 detector 配置")
    fusion = config.get("fusion", {})
    if fusion.get("type") != "weighted" or fusion.get("classifier", {}).get("type") != "classifier_mean":
        raise ValueError("Scratch V5 仅支持 weighted + classifier_mean 融合")

    names = [str(item.get("name", "")) for item in classifiers]
    if len(set(names)) != 2 or set(fusion["classifier"].get("models", [])) != set(names):
        raise ValueError("Scratch V5 融合模型名称与分类器不一致")
    threshold = float(config.get("default_threshold", -1.0))
    alpha = float(fusion.get("alpha", -1.0))
    if not 0.0 < threshold < 1.0 or not 0.0 <= alpha <= 1.0:
        raise ValueError("Scratch V5 阈值或融合权重超出范围")

    for item in classifiers:
        if item.get("family") not in {"efficientnet_b0", "resnet18"}:
            raise ValueError(f"不支持的 Scratch V5 分类器配置：{item.get('family')}")
        if int(item.get("imgsz", 0)) < 1 or float(item.get("temperature", 0.0)) <= 0.0:
            raise ValueError(f"Scratch V5 分类器尺寸或温度无效：{item.get('name')}")
        if item.get("tta", "none") != "none":
            raise ValueError("当前 Scratch V5 运行时仅支持 tta=none")
    detector = config["detector"]
    if int(detector.get("imgsz", 0)) < 1 or float(detector.get("temperature", 0.0)) <= 0.0:
        raise ValueError("Scratch V5 detector 尺寸或温度无效")
    if not 0.0 < float(detector.get("conf_floor", -1.0)) < 1.0:
        raise ValueError("Scratch V5 detector conf_floor 超出范围")
    if not 0.0 < float(detector.get("iou", -1.0)) <= 1.0:
        raise ValueError("Scratch V5 detector iou 超出范围")

    for item in [*classifiers, detector]:
        weight = Path(str(item.get("weights", "")))
        if not weight.is_absolute():
            weight = path.parent / weight
        weight = weight.resolve()
        if not weight.is_file():
            raise FileNotFoundError(f"找不到 Scratch V5 权重：{weight}")
        expected = str(item.get("sha256", "")).lower()
        if verify_hashes and (not expected or _sha256(weight) != expected):
            raise ValueError(f"Scratch V5 权重校验失败：{weight.name}")
        item["weights"] = weight
    config["config_path"] = path
    return config


class ScratchV5Runtime:
    """Load the two classifiers and auxiliary detector once per worker."""

    def __init__(self, config_path, device=None, warmup=True):
        import torch
        from torchvision import transforms
        from ultralytics import YOLO

        self.config = load_model2_config(config_path)
        self.version = self.config["version"]
        self.torch = torch
        self.device = torch.device(device or ("cuda:0" if torch.cuda.is_available() else "cpu"))
        self.yolo_device = 0 if self.device.type == "cuda" else "cpu"
        self.tensor_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        self.classifiers = [self._load_classifier(item) for item in self.config["classifiers"]]
        self.detector = YOLO(str(self.config["detector"]["weights"]), task="detect")
        if set(self.detector.names.values()) != {"scratch"}:
            raise ValueError("Scratch V5 detector 必须是单类别 scratch 模型")
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
        family = str(checkpoint.get("family", ""))
        size = int(checkpoint.get("size", 0))
        if family != item["family"] or size != int(item["imgsz"]):
            raise ValueError(f"分类器元数据与配置不一致：{item['name']}")
        state_dict = checkpoint.get("model", checkpoint)
        if family == "efficientnet_b0":
            model = efficientnet_b0(weights=None)
            outputs = int(state_dict["classifier.1.weight"].shape[0])
            model.classifier[1] = self.torch.nn.Linear(model.classifier[1].in_features, outputs)
        elif family == "resnet18":
            model = resnet18(weights=None)
            outputs = int(state_dict["fc.weight"].shape[0])
            model.fc = self.torch.nn.Linear(model.fc.in_features, outputs)
        else:
            raise ValueError(f"不支持的 Scratch V5 分类器：{family}")
        if outputs != 1:
            raise ValueError(f"Scratch V5 分类器必须只有一个输出：{item['name']}")
        model.load_state_dict(state_dict)
        model.to(self.device).eval()
        return item, model

    def _warmup(self):
        with self.torch.inference_mode():
            for item, model in self.classifiers:
                model(self.torch.zeros((1, 3, int(item["imgsz"]), int(item["imgsz"])), device=self.device))
        detector = self.config["detector"]
        size = int(detector["imgsz"])
        self.detector.predict(
            np.zeros((size, size, 3), dtype=np.uint8),
            imgsz=size,
            conf=float(detector["conf_floor"]),
            iou=float(detector["iou"]),
            device=self.yolo_device,
            verbose=False,
        )

    def predict(self, crop):
        if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
            raise ValueError("Scratch V5 收到空齿轮 ROI")
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        classifier_scores = []
        with self.torch.inference_mode():
            for item, model in self.classifiers:
                image = square_rgb_image(rgb, int(item["imgsz"]))
                tensor = self.tensor_transform(image).unsqueeze(0).to(self.device)
                raw = float(model(tensor).sigmoid()[0, 0].item())
                classifier_scores.append(apply_temperature(raw, item.get("temperature", 1.0)))

        detector = self.config["detector"]
        result = self.detector.predict(
            crop,
            imgsz=int(detector["imgsz"]),
            conf=float(detector["conf_floor"]),
            iou=float(detector["iou"]),
            device=self.yolo_device,
            verbose=False,
        )[0]
        raw_detector = 0.0
        auxiliary_box = None
        if result.boxes is not None and len(result.boxes):
            confidences = result.boxes.conf.detach().cpu().numpy()
            best_index = int(np.argmax(confidences))
            raw_detector = float(confidences[best_index])
            if raw_detector >= float(detector.get("display_confidence", 0.05)):
                coordinates = result.boxes.xyxy[best_index].detach().cpu().tolist()
                auxiliary_box = _clip_box(coordinates, crop.shape)
        detector_score = apply_temperature(raw_detector, detector.get("temperature", 1.0))
        fused, classifier_score = fuse_probabilities(
            classifier_scores[0], classifier_scores[1], detector_score, self.config["fusion"]["alpha"]
        )
        values = (fused, classifier_score, detector_score)
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError("Scratch V5 输出包含 NaN 或 Inf")
        return ScratchV5Prediction(fused, classifier_score, detector_score, auxiliary_box)


def _clip_box(box, shape):
    height, width = shape[:2]
    x1, y1, x2, y2 = (int(round(value)) for value in box)
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)
