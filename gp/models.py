"""Two-stage gear location and defect classification pipeline."""

import time

import cv2

from .missing_hole import MissingHoleRuntime
from .scratch_v5 import ScratchV5Runtime
from .types import GearObservation, InspectionResult


class TwoStageInspector:
    """Locate gear ROIs, then run Scratch V5 and Missing Hole V1."""

    def __init__(self, config):
        config.validate_models()
        from ultralytics import YOLO

        self.config = config
        # Locator is a Ultralytics `.pt` or NX-built `.engine` via GEARPRO_MODEL1.
        self.locator = YOLO(str(config.locator_model), task="detect")
        self.model2 = ScratchV5Runtime(config.model2_config)
        self.missing_hole = MissingHoleRuntime(
            config.missing_hole_config,
            device=str(self.model2.device),
        )

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
        missing_cls1_ms = missing_cls2_ms = missing_det_ms = missing_fuse_ms = 0.0
        if located.boxes is not None:
            boxes = located.boxes.xyxy.detach().cpu().numpy()
            confidences = located.boxes.conf.detach().cpu().numpy()
            for box, confidence in zip(boxes, confidences):
                coordinates = self._clip_box(box, frame.shape)
                crop, crop_box = self._crop_with_margin(frame, coordinates)
                if crop.size == 0:
                    raise ValueError("Model1 生成了空齿轮 ROI")
                scratch = self.model2.predict(crop)
                missing = self.missing_hole.predict(crop)
                cls1_ms += scratch.classifier1_latency_ms
                cls2_ms += scratch.classifier2_latency_ms
                det_ms += scratch.detector_latency_ms
                fuse_ms += scratch.fusion_latency_ms
                missing_cls1_ms += missing.classifier1_latency_ms
                missing_cls2_ms += missing.classifier2_latency_ms
                missing_det_ms += missing.detector_latency_ms
                missing_fuse_ms += missing.fusion_latency_ms
                observation = GearObservation(
                    box=coordinates,
                    location_confidence=float(confidence),
                    defect_score=scratch.defect_score,
                    classifier_probability=scratch.classifier_probability,
                    detector_probability=scratch.detector_probability,
                    auxiliary_box=self._map_auxiliary_box(scratch.auxiliary_box, crop_box),
                    scratch_threshold=self.config.scratch_threshold,
                    scratch_reject=scratch.defect_score >= self.config.scratch_threshold,
                    missing_hole_probability=missing.probability,
                    missing_hole_classifier_probability=missing.classifier_probability,
                    missing_hole_detector_probability=missing.detector_probability,
                    missing_hole_auxiliary_box=self._map_auxiliary_box(missing.auxiliary_box, crop_box),
                    missing_hole_threshold=self.config.missing_hole_threshold,
                    missing_hole_reject=missing.probability >= self.config.missing_hole_threshold,
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
            defect_threshold=self.config.scratch_threshold,
            model_version=self.model2.version,
            missing_hole_classifier1_latency_ms=missing_cls1_ms,
            missing_hole_classifier2_latency_ms=missing_cls2_ms,
            missing_hole_detector_latency_ms=missing_det_ms,
            missing_hole_fusion_latency_ms=missing_fuse_ms,
            missing_hole_latency_ms=missing_cls1_ms + missing_cls2_ms + missing_det_ms + missing_fuse_ms,
            missing_hole_threshold=self.config.missing_hole_threshold,
            missing_hole_model_version=self.missing_hole.version,
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
        defective = observation.is_defective
        color = (40, 40, 220) if defective else (40, 190, 80)
        reason = "+".join(observation.reject_reasons).upper() or "GOOD"
        label = f"{'DEFECT' if defective else 'GOOD'} {reason}"
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
        if observation.missing_hole_auxiliary_box is not None:
            mx1, my1, mx2, my2 = observation.missing_hole_auxiliary_box
            cv2.rectangle(frame, (mx1, my1), (mx2, my2), (220, 120, 30), 2)
            cv2.putText(
                frame,
                "MISSING HOLE",
                (mx1, max(20, my1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (220, 120, 30),
                2,
            )
