"""GearPro runtime configuration and project paths."""

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass
class AppConfig:
    """Mutable settings shared by the UI and inspection worker."""

    camera_index: int = 2
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    serial_port: str = "/dev/ttyHS1"
    serial_baudrate: int = 9600
    locator_model: Path = PROJECT_ROOT / "model" / "model1.pt"
    classifier_model: Path = PROJECT_ROOT / "model" / "model2.pt"
    locator_confidence: float = 0.70
    locator_iou: float = 0.45
    defect_threshold: float = 0.50
    inference_interval: float = 0.10
    result_cooldown: float = 5.0
    mode: str = "自由模式"
    target_quantity: int = 100
    duration_minutes: int = 10

    @classmethod
    def from_environment(cls):
        """Build settings while allowing deployment-only environment overrides."""
        config = cls()
        config.camera_index = int(os.getenv("GEARPRO_CAMERA_INDEX", config.camera_index))
        config.serial_port = os.getenv("GEARPRO_SERIAL_PORT", config.serial_port)
        config.locator_model = Path(os.getenv("GEARPRO_MODEL1", str(config.locator_model)))
        config.classifier_model = Path(os.getenv("GEARPRO_MODEL2", str(config.classifier_model)))
        return config

    def validate_models(self):
        missing = [str(path) for path in (self.locator_model, self.classifier_model) if not path.is_file()]
        if missing:
            raise FileNotFoundError("找不到模型文件：" + "、".join(missing))
