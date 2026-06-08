import os
import threading
from pathlib import Path
from ultralytics import YOLO



#一些全局变量
frame_lock = threading.Lock()
results_lock = threading.Lock()
frame = None

MODEL_PATH = Path(os.environ.get("GP_MODEL_PATH", Path(__file__).resolve().parent / "best.pt"))
model = YOLO(str(MODEL_PATH))


detection_results = None

running = True
