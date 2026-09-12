from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))

from ultralytics import YOLO  # noqa: E402


def main() -> None:
    model = YOLO("yolo26n.pt")
    model.train(
        data=str(ROOT / "DATASET" / "data.yaml"),
        epochs=100,
        imgsz=640,
        batch=8,
        workers=0,
        device=0,
        project=str(ROOT / "runs"),
        name="gear_yolo26n_dataset",
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
