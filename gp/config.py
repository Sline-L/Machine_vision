"""GearPro runtime configuration and project paths."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    model2_config: Path = PROJECT_ROOT / "model" / "model2" / "inference_config.json"
    locator_confidence: float = 0.70
    locator_iou: float = 0.45
    defect_threshold: float = 0.300273610279458
    inference_interval: float = 0.10
    result_cooldown: float = 5.0
    mode: str = "自由模式"
    target_quantity: int = 100
    duration_minutes: int = 10
    video_path: Optional[Path] = None
    serial_enabled: bool = True

    @classmethod
    def from_environment(cls):
        """Build settings while allowing deployment-only environment overrides."""
        config = cls()
        config.camera_index = int(os.getenv("GEARPRO_CAMERA_INDEX", config.camera_index))
        config.serial_port = os.getenv("GEARPRO_SERIAL_PORT", config.serial_port)
        config.locator_model = Path(os.getenv("GEARPRO_MODEL1", str(config.locator_model)))
        config.model2_config = Path(os.getenv("GEARPRO_MODEL2", str(config.model2_config)))
        # Model1 may be .pt or .engine. Model2 is a Scratch V5 JSON bundle.
        if config.model2_config.is_file():
            try:
                model2 = json.loads(config.model2_config.read_text(encoding="utf-8"))
                config.defect_threshold = float(model2["default_threshold"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                # The worker reports the complete configuration error in the UI.
                pass
        return config

    def validate_models(self):
        missing = [str(path) for path in (self.locator_model, self.model2_config) if not path.is_file()]
        if missing:
            raise FileNotFoundError("找不到模型文件：" + "、".join(missing))
