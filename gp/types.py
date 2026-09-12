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


@dataclass
class InspectionResult:
    annotated_frame: Any
    observations: List[GearObservation] = field(default_factory=list)
    elapsed_ms: float = 0.0
    defect_threshold: float = 0.5
    model_version: str = ""

    @property
    def has_gear(self):
        return bool(self.observations)

    @property
    def is_defective(self):
        return any(item.defect_score >= self.defect_threshold for item in self.observations)

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
