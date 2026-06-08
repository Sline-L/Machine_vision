import threading
from PyQt5.QtWidgets import ( QLabel, QVBoxLayout, 
                             QWidget, QHBoxLayout, QTextEdit, QPushButton)

from PyQt5.QtCore import  Qt,QTimer


from gp_detectionworker import DetectionWorker
import gp_globals

import gp_serial

rest = 0



class DetectionDisplayWidget(QWidget):
    """右侧显示检测结果的控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setMinimumSize(640, 480)
        self.setStyleSheet("border: 2px solid #cccccc; background-color: #f8f9fa;")
        
        # 创建布局
        layout = QVBoxLayout(self)
        #@#
        self.timer = QTimer()
        self.timer.setSingleShot(True)  # 只触发一次
        self.timer.timeout.connect(self.on_timer_timeout)
        #####
        # 标题
        title = QLabel("YOLO检测结果")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 10px;
            background-color: #e8f4f8;
            border-radius: 5px;
            margin: 5px;
        """)
        layout.addWidget(title)
        
        # 结果显示区域
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 14px;
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.result_text)
        
        # 统计信息标签
        self.stats_label = QLabel("等待检测结果...")
        self.stats_label.setStyleSheet("""
            color: #27ae60;
            font-size: 14px;
            font-weight: bold;
            padding: 5px;
            background-color: #ecf0f1;
            border-radius: 3px;
        """)
        layout.addWidget(self.stats_label)
        
        # 检测频率控制
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("检测频率:"))
        
        self.freq_slider = QPushButton("正常 (0.1s)")
        self.freq_slider.clicked.connect(self.toggle_frequency)
        self.freq_slider.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        self.detection_interval = 0.1  # 默认100ms
        freq_layout.addWidget(self.freq_slider)
        freq_layout.addStretch()
        layout.addLayout(freq_layout)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        self.detect_btn = QPushButton("开始检测")
        self.detect_btn.clicked.connect(self.toggle_detection)
        self.detect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.clicked.connect(self.clear_results)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
        button_layout.addWidget(self.detect_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)
        
        # 创建工作线程对象
        self.worker = DetectionWorker()
        self.worker.detection_ready.connect(self.update_detection_display)
        self.worker.stats_updated.connect(self.stats_label.setText)
        self.worker.error_occurred.connect(self.show_error)
        
        self.detection_enabled = False
        self.worker_thread = None
       

    def on_timer_timeout(self):
        """定时器超时回调函数"""
        global rest
        rest = 0  # 2秒后重置为0，允许再次发送

    def toggle_frequency(self):
        """切换检测频率"""
        if self.detection_interval == 0.1:
            self.detection_interval = 0.3  # 300ms
            self.freq_slider.setText("低速 (0.3s)")
            self.freq_slider.setStyleSheet(self.freq_slider.styleSheet().replace("#3498db", "#f39c12"))
        elif self.detection_interval == 0.3:
            self.detection_interval = 0.5  # 500ms
            self.freq_slider.setText("更慢 (0.5s)")
            self.freq_slider.setStyleSheet(self.freq_slider.styleSheet().replace("#f39c12", "#e67e22"))
        else:
            self.detection_interval = 0.1  # 100ms
            self.freq_slider.setText("正常 (0.1s)")
            self.freq_slider.setStyleSheet(self.freq_slider.styleSheet().replace("#e67e22", "#3498db"))
        
    def toggle_detection(self):
        """切换检测状态"""
        self.detection_enabled = not self.detection_enabled
        
        if self.detection_enabled:
            self.detect_btn.setText("停止检测")
            self.detect_btn.setStyleSheet(self.detect_btn.styleSheet().replace("#3498db", "#e74c3c"))
            self.start_detection_thread()
        else:
            self.detect_btn.setText("开始检测")
            self.detect_btn.setStyleSheet(self.detect_btn.styleSheet().replace("#e74c3c", "#3498db"))
            self.stop_detection_thread()
    
    def start_detection_thread(self):
        """启动检测线程"""
        
        gp_globals.running = True
        
        # 创建线程
        self.worker_thread = threading.Thread(target=self.worker.start_detection)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def stop_detection_thread(self):
        """停止检测线程"""
        
        gp_globals.running = False
        self.worker.stop_detection()
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
    



    def update_detection_display(self, result):
        """更新检测结果显示（在主线程中执行）"""
        boxes = result.boxes
        global rest
        if len(boxes) > 0:
            # 获取检测信息
            cls_ids = boxes.cls.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            
            # 获取类别名称
            names = result.names
            
            # 显示详细信息
            display_text = "检测到的目标：\n"
            display_text += "=" * 40 + "\n"
            
            for i, cls_id in enumerate(cls_ids):
                class_name = names[cls_id]
                confidence = confs[i]
                display_text += f"• {class_name}: {confidence:.2%}\n"

                if class_name=="good" and rest==0:
                    gp_serial.serial_manager.send("01")
                    rest=1
                    self.timer.start(5000)  # 2000毫秒 = 2秒

                elif class_name=="miss"and rest==0:
                    gp_serial.serial_manager.send("02")
                    rest=1
                    self.timer.start(5000)  # 2000毫秒 = 2秒

            # 显示在文本区域
            self.result_text.setText(display_text)
        else:
            self.result_text.setText("未检测到目标")
    
    def clear_results(self):
        """清空结果显示"""
       
        self.result_text.clear()
        self.stats_label.setText("结果已清空")
        with gp_globals.results_lock:
            gp_globals.detection_results = None
    
    def show_error(self, error_msg):
        """显示错误信息"""
        self.stats_label.setText(f"错误: {error_msg}")
        self.stats_label.setStyleSheet(self.stats_label.styleSheet().replace("#27ae60", "#e74c3c"))
        
