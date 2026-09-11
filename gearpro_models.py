"""Two-stage gear location and defect classification pipeline."""

import time

import cv2
import numpy as np

from gearpro_types import GearObservation, InspectionResult


class TwoStageInspector:
    """Locate gear ROIs with YOLO, then classify each ROI with ResNet18."""

    def __init__(self, config):
        config.validate_models()
        import torch
        from torchvision.models import resnet18
        from ultralytics import YOLO

        self.config = config
        self.torch = torch
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.locator = YOLO(str(config.locator_model))

        checkpoint = self._load_checkpoint(config.classifier_model)
        state_dict = checkpoint.get("model", checkpoint)
        output_features = int(state_dict["fc.weight"].shape[0])
        self.classifier = resnet18(weights=None)
        self.classifier.fc = torch.nn.Linear(self.classifier.fc.in_features, output_features)
        self.classifier.load_state_dict(state_dict)
        self.classifier.to(self.device).eval()
        self.classifier_size = int(checkpoint.get("size", 512))
        self.output_features = output_features

    def _load_checkpoint(self, path):
        try:
            return self.torch.load(str(path), map_location="cpu", weights_only=True)
        except TypeError:
            return self.torch.load(str(path), map_location="cpu")

    def inspect(self, frame):
        started = time.perf_counter()
        located = self.locator.predict(
            source=frame,
            conf=self.config.locator_confidence,
            iou=self.config.locator_iou,
            verbose=False,
        )[0]
        observations = []
        annotated = frame.copy()
        if located.boxes is not None:
            boxes = located.boxes.xyxy.detach().cpu().numpy()
            confidences = located.boxes.conf.detach().cpu().numpy()
            for box, confidence in zip(boxes, confidences):
                coordinates = self._clip_box(box, frame.shape)
                crop = self._crop_with_margin(frame, coordinates)
                if crop.size == 0:
                    continue
                score = self._defect_score(crop)
                observation = GearObservation(coordinates, float(confidence), score)
                observations.append(observation)
                self._draw_observation(annotated, observation)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return InspectionResult(
            annotated_frame=annotated,
            observations=observations,
            elapsed_ms=elapsed_ms,
            defect_threshold=self.config.defect_threshold,
        )

    def _defect_score(self, crop):
        image = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (self.classifier_size, self.classifier_size), interpolation=cv2.INTER_LINEAR)
        tensor = self.torch.from_numpy(np.ascontiguousarray(image.transpose(2, 0, 1))).float().div_(255.0)
        mean = tensor.new_tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
        std = tensor.new_tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
        tensor = tensor.sub_(mean).div_(std).unsqueeze(0).to(self.device)
        with self.torch.inference_mode():
            output = self.classifier(tensor)
            if self.output_features == 1:
                return float(output.sigmoid()[0, 0].item())
            return float(output.softmax(dim=1)[0, 1].item())

    @staticmethod
    def _clip_box(box, shape):
        height, width = shape[:2]
        x1, y1, x2, y2 = (int(round(value)) for value in box)
        return max(0, x1), max(0, y1), min(width, x2), min(height, y2)

    @staticmethod
    def _crop_with_margin(frame, box):
        x1, y1, x2, y2 = box
        margin_x = int((x2 - x1) * 0.04)
        margin_y = int((y2 - y1) * 0.04)
        height, width = frame.shape[:2]
        return frame[max(0, y1 - margin_y):min(height, y2 + margin_y),
                     max(0, x1 - margin_x):min(width, x2 + margin_x)]

    def _draw_observation(self, frame, observation):
        x1, y1, x2, y2 = observation.box
        defective = observation.defect_score >= self.config.defect_threshold
        color = (40, 40, 220) if defective else (40, 190, 80)
        label = f"{'DEFECT' if defective else 'GOOD'} {observation.defect_score:.1%}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
