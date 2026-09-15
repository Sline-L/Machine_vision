"""Helpers for one-click GearPro starters."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORTS = PROJECT_ROOT / ".cache" / "exports"


def start(locator=None, model2_config=None, missing_hole_config=None, camera_index=0):
    """Set deployment env vars, then start the normal GearPro Web service."""
    os.chdir(PROJECT_ROOT)
    os.environ["GEARPRO_CAMERA_INDEX"] = str(camera_index)
    if locator is not None:
        locator = Path(locator)
        if not locator.is_file():
            print(f"找不到定位模型：{locator}", file=sys.stderr)
            print("engine 只在 NX 上用 export_engine.py 生成，位于 .cache/exports/", file=sys.stderr)
            return 1
        os.environ["GEARPRO_MODEL1"] = str(locator.resolve())
    if model2_config is not None:
        model2_config = Path(model2_config)
        if not model2_config.is_file():
            print(f"找不到 Model2 配置：{model2_config}", file=sys.stderr)
            return 1
        os.environ["GEARPRO_MODEL2"] = str(model2_config.resolve())
    if missing_hole_config is not None:
        missing_hole_config = Path(missing_hole_config)
        if not missing_hole_config.is_file():
            print(f"找不到 Missing Hole 配置：{missing_hole_config}", file=sys.stderr)
            return 1
        os.environ["GEARPRO_MISSING_HOLE_MODEL"] = str(missing_hole_config.resolve())
    from .app import main
    return main()
