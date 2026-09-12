"""Export Model1 from `.pt` to TensorRT `.engine` on the target Jetson."""

from pathlib import Path
import shutil

from .launch import EXPORTS, PROJECT_ROOT

DEFAULT_SOURCE = PROJECT_ROOT / "model" / "model1.pt"
DEFAULT_DEST = EXPORTS / "model1.engine"


def export_locator_engine(source=DEFAULT_SOURCE, dest=DEFAULT_DEST, imgsz=640):
    """Build an FP16 TensorRT engine for the gear locator.

    Ultralytics still writes a temporary ONNX file while compiling. That file is
    deleted afterwards; inference only uses `.pt` and `.engine`.
    """
    import torch
    from ultralytics import YOLO

    source = Path(source).expanduser().resolve()
    dest = Path(dest).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到定位模型：{source}")
    if not torch.cuda.is_available():
        raise RuntimeError("导出 engine 需要 CUDA，请在 Jetson NX 上运行 export_engine.py")

    dest.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(source), task="detect")
    exported = Path(
        model.export(
            format="engine",
            imgsz=imgsz,
            batch=1,
            half=True,
            dynamic=False,
            nms=False,
            device=0,
            workspace=4,
        )
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(exported), dest)

    leftovers = {
        source.with_suffix(".onnx"),
        exported.with_suffix(".onnx"),
        Path(str(exported) + ".onnx"),
    }
    for leftover in leftovers:
        if leftover.is_file():
            leftover.unlink()
    return dest
