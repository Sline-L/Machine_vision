"""Small data objects passed between GearPro components."""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class GearObservation:
    box: Tuple[int, int, int, int]
    location_confidence: float
    defect_score: float
    classifier_probability: float = 0.0
    detector_probability: float = 0.0
    auxiliary_box: Optional[Tuple[int, int, int, int]] = None
    scratch_threshold: float = 0.5
    scratch_reject: Optional[bool] = None
    missing_hole_probability: float = 0.0
    missing_hole_classifier_probability: float = 0.0
    missing_hole_detector_probability: float = 0.0
    missing_hole_auxiliary_box: Optional[Tuple[int, int, int, int]] = None
    missing_hole_threshold: float = 0.5
    missing_hole_reject: bool = False

    @property
    def scratch_is_reject(self):
        return self.defect_score >= self.scratch_threshold if self.scratch_reject is None else self.scratch_reject

    @property
    def is_defective(self):
        return self.scratch_is_reject or self.missing_hole_reject

    @property
    def reject_reasons(self):
        reasons = []
        if self.scratch_is_reject:
            reasons.append("scratch")
        if self.missing_hole_reject:
            reasons.append("missing_hole")
        return reasons


@dataclass
class InspectionResult:
    annotated_frame: Any
    observations: List[GearObservation] = field(default_factory=list)
    elapsed_ms: float = 0.0
    locator_latency_ms: float = 0.0
    classifier1_latency_ms: float = 0.0
    classifier2_latency_ms: float = 0.0
    detector_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    scratch_latency_ms: float = 0.0
    defect_threshold: float = 0.5
    model_version: str = ""
    missing_hole_classifier1_latency_ms: float = 0.0
    missing_hole_classifier2_latency_ms: float = 0.0
    missing_hole_detector_latency_ms: float = 0.0
    missing_hole_fusion_latency_ms: float = 0.0
    missing_hole_latency_ms: float = 0.0
    missing_hole_threshold: float = 0.5
    missing_hole_model_version: str = ""
    source_frame_seq: Optional[int] = None
    source_capture_ts: Optional[float] = None
    inspection_start_ts: Optional[float] = None
    inspection_end_ts: Optional[float] = None
    latest_frame_seq_at_completion: Optional[int] = None

    @property
    def inspection_age_ms(self):
        if self.source_capture_ts is None or self.inspection_end_ts is None:
            return None
        return (float(self.inspection_end_ts) - float(self.source_capture_ts)) * 1000.0

    @property
    def frame_lag(self):
        if self.source_frame_seq is None or self.latest_frame_seq_at_completion is None:
            return None
        return int(self.latest_frame_seq_at_completion) - int(self.source_frame_seq)

    @property
    def has_gear(self):
        return bool(self.observations)

    @property
    def is_defective(self):
        return any(
            (item.defect_score >= self.defect_threshold or item.missing_hole_reject)
            if item.scratch_reject is None
            else item.is_defective
            for item in self.observations
        )

    @property
    def reject_reasons(self):
        reasons = []
        if any(
            item.defect_score >= self.defect_threshold if item.scratch_reject is None else item.scratch_reject
            for item in self.observations
        ):
            reasons.append("scratch")
        if any(item.missing_hole_reject for item in self.observations):
            reasons.append("missing_hole")
        return reasons

    @property
    def verdict(self):
        if not self.has_gear:
            return "未检测到齿轮"
        return "不合格" if self.is_defective else "合格"


@dataclass
class InspectionStats:
    total: int = 0
    good: int = 0
    defective: int = 0

    def add(self, is_defective):
        self.total += 1
        if is_defective:
            self.defective += 1
        else:
            self.good += 1

    def clear(self):
        self.total = self.good = self.defective = 0
