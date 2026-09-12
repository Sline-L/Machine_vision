"""Helpers for one-click GearPro starters."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORTS = PROJECT_ROOT / ".cache" / "exports"


def start(locator=None, model2_config=None, camera_index=0):
    """Set deployment env vars, then open the normal GearPro window."""
    os.chdir(PROJECT_ROOT)
    os.environ["GEARPRO_CAMERA_INDEX"] = str(camera_index)
    if locator is not None:
        locator = Path(locator)
        if not locator.is_file():
            print(f"找不到定位模型：{locator}", file=sys.stderr)
            print("engine / onnx 只在 NX 上导出后存在于 .cache/exports/", file=sys.stderr)
            return 1
        os.environ["GEARPRO_MODEL1"] = str(locator.resolve())
    if model2_config is not None:
        model2_config = Path(model2_config)
        if not model2_config.is_file():
            print(f"找不到 Model2 配置：{model2_config}", file=sys.stderr)
            return 1
        os.environ["GEARPRO_MODEL2"] = str(model2_config.resolve())
    from .app import main
    return main()
