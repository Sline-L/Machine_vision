import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class GlobalSettingsWidget(QWidget):
    """全局设置界面，包含三个可切换的子界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        # 创建主布局
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)  # 选项卡在上侧
        
        # 创建三个子界面
        self.free_mode_widget = FreeModeWidget()
        self.quantitative_mode_widget = QuantitativeModeWidget()
        self.timed_mode_widget = TimedModeWidget()
        
        # 添加选项卡
        self.tab_widget.addTab(self.free_mode_widget, "自由模式")
        self.tab_widget.addTab(self.quantitative_mode_widget, "定量模式")
        self.tab_widget.addTab(self.timed_mode_widget, "定时模式")
        
        # 添加返回按钮
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("返回主界面")
        self.back_button.setFixedSize(120, 30)
        button_layout.addStretch()
        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        
        # 添加到主布局
        main_layout.addWidget(self.tab_widget)
        main_layout.addLayout(button_layout)


class FreeModeWidget(QWidget):
    """自由模式界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 添加一些示例控件
        label = QLabel("自由模式设置")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        # 示例参数设置
        param_group = QGroupBox("参数设置")
        param_layout = QFormLayout()
        
        self.param1_edit = QLineEdit()
        self.param1_edit.setPlaceholderText("请输入参数1")
        self.param2_edit = QLineEdit()
        self.param2_edit.setPlaceholderText("请输入参数2")
        
        param_layout.addRow("参数1:", self.param1_edit)
        param_layout.addRow("参数2:", self.param2_edit)
        param_group.setLayout(param_layout)
        
        layout.addWidget(label)
        layout.addWidget(param_group)
        layout.addStretch()


class QuantitativeModeWidget(QWidget):
    """定量模式界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 添加一些示例控件
        label = QLabel("定量模式设置")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        # 数量设置
        spin_group = QGroupBox("数量设置")
        spin_layout = QFormLayout()
        
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 1000)
        self.quantity_spin.setValue(10)
        
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.1, 100.0)
        self.threshold_spin.setValue(1.0)
        self.threshold_spin.setSingleStep(0.1)
        
        spin_layout.addRow("数量:", self.quantity_spin)
        spin_layout.addRow("阈值:", self.threshold_spin)
        spin_group.setLayout(spin_layout)
        
        layout.addWidget(label)
        layout.addWidget(spin_group)
        layout.addStretch()


class TimedModeWidget(QWidget):
    """定时模式界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 添加一些示例控件
        label = QLabel("定时模式设置")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        # 时间设置
        time_group = QGroupBox("时间设置")
        time_layout = QFormLayout()
        
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setTime(QTime.currentTime())
        
        self.duration_edit = QTimeEdit()
        self.duration_edit.setTime(QTime(0, 1, 0))  # 默认1分钟
        
        time_layout.addRow("开始时间:", self.start_time_edit)
        time_layout.addRow("持续时间:", self.duration_edit)
        time_group.setLayout(time_layout)
        
        layout.addWidget(label)
        layout.addWidget(time_group)
        layout.addStretch()


class CaptureModeWidget(QWidget):
    """拍摄模式界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title = QLabel("拍摄模式")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        
        # 拍摄控制
        control_group = QGroupBox("拍摄控制")
        control_layout = QVBoxLayout()
        
        self.capture_button = QPushButton("开始拍摄")
        self.capture_button.setFixedSize(150, 50)
        self.capture_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-size: 14px; }"
                                         "QPushButton:hover { background-color: #45a049; }")
        
        self.stop_button = QPushButton("停止拍摄")
        self.stop_button.setFixedSize(150, 50)
        self.stop_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-size: 14px; }"
                                      "QPushButton:hover { background-color: #da190b; }")
        
        # 拍摄参数
        param_group = QGroupBox("拍摄参数")
        param_layout = QFormLayout()
        
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1920x1080", "1280x720", "640x480"])
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPG", "PNG", "BMP"])
        
        param_layout.addRow("分辨率:", self.resolution_combo)
        param_layout.addRow("格式:", self.format_combo)
        param_group.setLayout(param_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.capture_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        
        control_layout.addLayout(button_layout)
        control_group.setLayout(control_layout)
        
        # 返回按钮
        self.back_button = QPushButton("返回主界面")
        self.back_button.setFixedSize(120, 30)
        
        back_layout = QHBoxLayout()
        back_layout.addStretch()
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        
        # 添加到主布局
        layout.addWidget(title)
        layout.addWidget(control_group)
        layout.addWidget(param_group)
        layout.addStretch()
        layout.addLayout(back_layout)


class CalibrationModeWidget(QWidget):
    """校准模式界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title = QLabel("自由模式（校准）")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        
        # 校准进度
        progress_group = QGroupBox("校准进度")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        progress_group.setLayout(progress_layout)
        
        # 校准按钮
        self.start_calib_button = QPushButton("开始校准")
        self.start_calib_button.setFixedSize(150, 40)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.start_calib_button)
        button_layout.addStretch()
        
        # 返回按钮
        self.back_button = QPushButton("返回主界面")
        self.back_button.setFixedSize(120, 30)
        
        back_layout = QHBoxLayout()
        back_layout.addStretch()
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        
        layout.addWidget(title)
        layout.addWidget(progress_group)
        layout.addLayout(button_layout)
        layout.addStretch()
        layout.addLayout(back_layout)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("多模式控制系统")
        self.setGeometry(300, 300, 800, 600)
        
        # 设置中心窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 创建堆叠窗口
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        # 创建主界面
        self.main_interface = self.create_main_interface()
        self.stacked_widget.addWidget(self.main_interface)
        
        # 创建其他界面
        self.global_settings = GlobalSettingsWidget()
        self.free_calibration = CalibrationModeWidget()
        self.quantitative_mode = QuantitativeModeWidget()
        self.timed_mode = TimedModeWidget()
        self.capture_mode = CaptureModeWidget()
        
        # 添加到堆叠窗口
        self.stacked_widget.addWidget(self.global_settings)
        self.stacked_widget.addWidget(self.free_calibration)
        self.stacked_widget.addWidget(self.quantitative_mode)
        self.stacked_widget.addWidget(self.timed_mode)
        self.stacked_widget.addWidget(self.capture_mode)
        
        # 连接信号
        self.connect_signals()
        
    def create_main_interface(self):
        """创建主界面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("主菜单")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 20px;")
        
        # 按钮样式
        button_style = """
            QPushButton {
                font-size: 14px;
                min-width: 150px;
                min-height: 50px;
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """
        
        # 创建按钮
        self.btn_global = QPushButton("全局设置")
        self.btn_free = QPushButton("自由模式（校准）")
        self.btn_quantitative = QPushButton("定量模式")
        self.btn_timed = QPushButton("定时模式")
        self.btn_capture = QPushButton("拍摄模式")
        
        # 应用样式
        for btn in [self.btn_global, self.btn_free, self.btn_quantitative, 
                   self.btn_timed, self.btn_capture]:
            btn.setStyleSheet(button_style)
        
        # 添加按钮到布局
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.btn_global, 0, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.btn_free, 0, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.btn_quantitative, 0, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.btn_timed, 0, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.btn_capture, 0, Qt.AlignCenter)
        layout.addStretch()
        
        return widget
    
    def connect_signals(self):
        """连接信号和槽"""
        # 主界面按钮连接
        self.btn_global.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.global_settings))
        self.btn_free.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.free_calibration))
        self.btn_quantitative.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.quantitative_mode))
        self.btn_timed.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.timed_mode))
        self.btn_capture.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.capture_mode))
        
        # 返回按钮连接
        self.global_settings.back_button.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.main_interface))
        self.free_calibration.back_button.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.main_interface))
        self.capture_mode.back_button.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.main_interface))
        
        # 校准按钮连接示例
        self.free_calibration.start_calib_button.clicked.connect(self.start_calibration)
        
    def start_calibration(self):
        """开始校准的示例功能"""
        self.free_calibration.status_label.setText("校准中...")
        self.free_calibration.progress_bar.setValue(50)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())