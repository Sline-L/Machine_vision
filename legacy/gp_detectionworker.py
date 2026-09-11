import time
from PyQt5.QtCore import pyqtSignal, QObject

import gp_globals 
#import gp_serial

class DetectionWorker(QObject):
    """工作线程类，用于处理YOLO检测"""
    detection_ready = pyqtSignal(object)  # 检测完成信号
    stats_updated = pyqtSignal(str)       # 统计信息更新信号
    error_occurred = pyqtSignal(str)      # 错误信号
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.detection_enabled = False

        
        
    def start_detection(self):
        """开始检测"""
        self.running = True
        self.detection_enabled = True
        self.detection_loop()


    
    def stop_detection(self):
        """停止检测"""
        self.detection_enabled = False
        self.running = False
    
    def detection_loop(self):
        """YOLO检测循环"""
        
        print("YOLO检测线程已启动")
        
        while self.running and self.detection_enabled:
            current_frame = None
            with gp_globals.frame_lock:
                if gp_globals.frame is not None:
                    current_frame = gp_globals.frame.copy()
            
            if current_frame is not None:
                try:
                    # 执行YOLO检测
                    results = gp_globals.model(current_frame, show=False, verbose=False,conf=0.7)
                    
                    # 更新检测结果
                    with gp_globals.results_lock:
                        gp_globals.detection_results = results[0]
                    
                    # 发送信号到主线程更新UI
                    self.detection_ready.emit(results[0])
                    
                    # 生成统计信息
                    boxes = results[0].boxes
                    if len(boxes) > 0:
                        cls_ids = boxes.cls.cpu().numpy().astype(int)

                        
                           
                        

                        names = results[0].names
                        
                        # 统计各类别数量
                        class_counts = {}
                        for cls_id in cls_ids:
                            class_name = names[cls_id]
                            class_counts[class_name] = class_counts.get(class_name, 0) + 1
                        
                        total = len(boxes)
                        stats = " | ".join([f"{name}: {count}" for name, count in class_counts.items()])
                        stats_text = f"检测到 {total} 个目标 | {stats}"
                        self.stats_updated.emit(stats_text)
                    else:
                        self.stats_updated.emit("未检测到目标")
                    
                except Exception as e:
                    self.error_occurred.emit(str(e))
            
            time.sleep(0.1)  # 控制检测频率
        
        print("YOLO检测线程结束")
