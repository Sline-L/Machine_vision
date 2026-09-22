"""Two-stage gear location and defect classification pipeline."""

import time

import cv2

from .scratch_v5 import ScratchV5Runtime
from .types import GearObservation, InspectionResult


class TwoStageInspector:
    """Locate gear ROIs with YOLO, then inspect each ROI with Scratch V5."""

    def __init__(self, config):
        config.validate_models()
        from ultralytics import YOLO

        self.config = config
        # Locator is a Ultralytics `.pt` or NX-built `.engine` via GEARPRO_MODEL1.
        self.locator = YOLO(str(config.locator_model), task="detect")
        self.model2 = ScratchV5Runtime(config.model2_config)

    def inspect(self, frame):
        started = time.perf_counter()
        located = self.locator.predict(
            source=frame,
            conf=self.config.locator_confidence,
            iou=self.config.locator_iou,
            verbose=False,
        )[0]
        locator_ms = (time.perf_counter() - started) * 1000
        observations = []
        annotated = frame.copy()
        cls1_ms = cls2_ms = det_ms = fuse_ms = 0.0
        if located.boxes is not None:
            boxes = located.boxes.xyxy.detach().cpu().numpy()
            confidences = located.boxes.conf.detach().cpu().numpy()
            for box, confidence in zip(boxes, confidences):
                coordinates = self._clip_box(box, frame.shape)
                crop, crop_box = self._crop_with_margin(frame, coordinates)
                if crop.size == 0:
                    raise ValueError("Model1 生成了空齿轮 ROI")
                prediction = self.model2.predict(crop)
                cls1_ms += prediction.classifier1_latency_ms
                cls2_ms += prediction.classifier2_latency_ms
                det_ms += prediction.detector_latency_ms
                fuse_ms += prediction.fusion_latency_ms
                auxiliary_box = self._map_auxiliary_box(prediction.auxiliary_box, crop_box)
                observation = GearObservation(
                    coordinates,
                    float(confidence),
                    prediction.defect_score,
                    prediction.classifier_probability,
                    prediction.detector_probability,
                    auxiliary_box,
                )
                observations.append(observation)
                self._draw_observation(annotated, observation)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return InspectionResult(
            annotated_frame=annotated,
            observations=observations,
            elapsed_ms=elapsed_ms,
            locator_latency_ms=locator_ms,
            classifier1_latency_ms=cls1_ms,
            classifier2_latency_ms=cls2_ms,
            detector_latency_ms=det_ms,
            fusion_latency_ms=fuse_ms,
            scratch_latency_ms=cls1_ms + cls2_ms + det_ms + fuse_ms,
            defect_threshold=self.config.defect_threshold,
            model_version=self.model2.version,
        )

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
        crop_box = (
            max(0, x1 - margin_x),
            max(0, y1 - margin_y),
            min(width, x2 + margin_x),
            min(height, y2 + margin_y),
        )
        cx1, cy1, cx2, cy2 = crop_box
        return frame[cy1:cy2, cx1:cx2], crop_box

    @staticmethod
    def _map_auxiliary_box(box, crop_box):
        if box is None:
            return None
        x1, y1, x2, y2 = box
        crop_x, crop_y = crop_box[:2]
        return x1 + crop_x, y1 + crop_y, x2 + crop_x, y2 + crop_y

    def _draw_observation(self, frame, observation):
        x1, y1, x2, y2 = observation.box
        defective = observation.defect_score >= self.config.defect_threshold
        color = (40, 40, 220) if defective else (40, 190, 80)
        label = f"{'DEFECT' if defective else 'GOOD'} {observation.defect_score:.1%}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        if observation.auxiliary_box is not None:
            sx1, sy1, sx2, sy2 = observation.auxiliary_box
            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), (0, 170, 255), 2)
            cv2.putText(
                frame,
                "SCRATCH",
                (sx1, max(20, sy1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 170, 255),
                2,
            )
