from ultralytics import YOLO

model = YOLO("/home/fibo/Desktop/QT/best.pt")

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