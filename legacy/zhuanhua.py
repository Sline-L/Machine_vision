from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO

model = YOLO(str(Path(__file__).resolve().parent / "models" / "best.pt"))

model.export(
    format="onnx",
    imgsz=(640,640),
    keras=False,
    optimize=False,
    half=False,
    int8=False,
    dynamic=False,
    simplify=True,
    opset=12,
    workspace=4.0,
    nms=False,
    batch=1,
    device="cpu"
)
