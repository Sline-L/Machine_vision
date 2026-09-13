"""GearPro runtime configuration, persistence, and project paths."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / "var"
SETTINGS_FILE = RUNTIME_ROOT / "settings.json"
LAST_GOOD_FILE = RUNTIME_ROOT / "settings.last_known_good.json"

PERSISTED_FIELDS = (
    "camera_index",
    "camera_width",
    "camera_height",
    "camera_fps",
    "serial_port",
    "serial_baudrate",
    "locator_confidence",
    "locator_iou",
    "defect_threshold",
    "inference_interval",
    "result_cooldown",
    "inference_profile",
    "ui_refresh_hz",
    "mode",
    "target_quantity",
    "duration_minutes",
    "stream_fps",
    "stream_quality",
)


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
    inference_profile: str = "FULL"
    ui_refresh_hz: float = 15.0
    mode: str = "自由模式"
    target_quantity: int = 100
    duration_minutes: int = 10
    video_path: Optional[Path] = None
    serial_enabled: bool = True
    stream_fps: float = 10.0
    stream_quality: int = 75

    @classmethod
    def from_environment(cls):
        """Build settings while allowing deployment-only environment overrides."""
        config = cls()
        persisted = config.load_persisted()
        if not persisted:
            persisted = config.load_persisted(LAST_GOOD_FILE)
        config.camera_index = int(os.getenv("GEARPRO_CAMERA_INDEX", config.camera_index))
        config.serial_port = os.getenv("GEARPRO_SERIAL_PORT", config.serial_port)
        config.locator_model = Path(os.getenv("GEARPRO_MODEL1", str(config.locator_model)))
        config.model2_config = Path(os.getenv("GEARPRO_MODEL2", str(config.model2_config)))
        # Model1 may be .pt or .engine. Model2 is a Scratch V5 JSON bundle.
        if config.model2_config.is_file() and "defect_threshold" not in persisted:
            try:
                model2 = json.loads(config.model2_config.read_text(encoding="utf-8"))
                config.defect_threshold = float(model2["default_threshold"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                # The worker reports the complete configuration error in the UI.
                pass
        return config

    def load_persisted(self, path=None):
        path = SETTINGS_FILE if path is None else Path(path)
        if not path.is_file():
            return set()
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if not isinstance(values, dict):
            return set()
        filtered = {name: values[name] for name in PERSISTED_FIELDS if name in values}
        try:
            self.update(filtered)
        except ValueError:
            return set()
        locator = values.get("locator_model")
        if isinstance(locator, str) and locator.strip():
            self.locator_model = Path(locator)
            filtered["locator_model"] = locator
        return set(filtered)

    def persist(self, path=None):
        """Atomically save operator-adjustable, non-secret settings."""
        path = SETTINGS_FILE if path is None else Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: getattr(self, name) for name in PERSISTED_FIELDS}
        payload["locator_model"] = str(self.locator_model)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def persist_last_known_good(self):
        """Promote the current in-memory config only after function/mission verify."""
        LAST_GOOD_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: getattr(self, name) for name in PERSISTED_FIELDS}
        payload["locator_model"] = str(self.locator_model)
        good_tmp = LAST_GOOD_FILE.with_suffix(LAST_GOOD_FILE.suffix + ".tmp")
        good_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        good_tmp.replace(LAST_GOOD_FILE)

    def update(self, values):
        """Validate and apply settings received from the Web UI."""
        unknown = sorted(set(values) - set(PERSISTED_FIELDS))
        if unknown:
            raise ValueError("不支持的设置：" + "、".join(unknown))
        candidate = {name: getattr(self, name) for name in PERSISTED_FIELDS}
        candidate.update(values)
        numeric_ranges = {
            "camera_index": (0, 32),
            "camera_width": (160, 7680),
            "camera_height": (120, 4320),
            "camera_fps": (1, 240),
            "serial_baudrate": (300, 4_000_000),
            "locator_confidence": (0.01, 0.99),
            "locator_iou": (0.01, 0.99),
            "defect_threshold": (0.01, 0.99),
            "inference_interval": (0.03, 5.0),
            "result_cooldown": (0.0, 3600.0),
            "ui_refresh_hz": (1.0, 60.0),
            "target_quantity": (1, 100000),
            "duration_minutes": (1, 1440),
            "stream_fps": (1.0, 30.0),
            "stream_quality": (30, 95),
        }
        for name, (minimum, maximum) in numeric_ranges.items():
            value = candidate[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} 必须是数字")
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} 必须位于 {minimum} 到 {maximum} 之间")
        integer_fields = {
            "camera_index",
            "camera_width",
            "camera_height",
            "camera_fps",
            "serial_baudrate",
            "target_quantity",
            "duration_minutes",
            "stream_quality",
        }
        for name in integer_fields:
            if not isinstance(candidate[name], int):
                raise ValueError(f"{name} 必须是整数")
        if candidate["mode"] not in ("自由模式", "定量模式", "定时模式", "视频测试模式"):
            raise ValueError("无效的运行模式")
        from .profiles import IMPLEMENTED
        if candidate["inference_profile"] not in IMPLEMENTED:
            raise ValueError("无效的推理档位")
        if not isinstance(candidate["serial_port"], str) or not candidate["serial_port"].strip():
            raise ValueError("串口路径不能为空")
        for name, value in values.items():
            setattr(self, name, value)

    def validate_models(self):
        missing = [str(path) for path in (self.locator_model, self.model2_config) if not path.is_file()]
        if missing:
            raise FileNotFoundError("找不到模型文件：" + "、".join(missing))


def load_last_known_good_snapshot():
    """Disk fallback used by rollback when no in-memory Control snapshot exists."""
    if not LAST_GOOD_FILE.is_file():
        return None
    try:
        values = json.loads(LAST_GOOD_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(values, dict):
        return None
    locator = values.get("locator_model")
    if not isinstance(locator, str) or not locator.strip():
        return None
    fields = {name: values[name] for name in PERSISTED_FIELDS if name in values}
    return {
        "locator_model": locator,
        "fields": fields,
        "inference_profile": values.get("inference_profile", "FULL"),
        "inspection_active": False,
    }
