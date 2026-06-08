import threading
from ultralytics import YOLO



#一些全局变量
frame_lock = threading.Lock()
results_lock = threading.Lock()
frame = None

model = YOLO("/home/fibo/Desktop/ultralytics-8.4.13/gear.pt")


detection_results = None

running = True
