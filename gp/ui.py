"""Main window and settings UI for GearPro."""

from pathlib import Path
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraView, LatestFrame, frame_to_pixmap
from .guardian import thermal_stop_needed
from .profiles import IMPLEMENTED, ProfileError, SPECS, apply_to_config
from .serial_io import SerialOutput
from .telemetry import build_snapshot
from .types import InspectionStats
from .worker import InspectionThread


class StatsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stats = InspectionStats()
        self.setMinimumHeight(120)

    def set_stats(self, stats):
        self.stats = stats
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        values = (("合格", self.stats.good, "#16a34a"), ("不合格", self.stats.defective, "#dc2626"))
        maximum = max(1, self.stats.good, self.stats.defective)
        bar_width = max(50, self.width() // 5)
        base_y = self.height() - 34
        for index, (label, value, color) in enumerate(values):
            x = self.width() // 4 + index * self.width() // 2 - bar_width // 2
            height = int(max(0, self.height() - 70) * value / maximum)
            painter.fillRect(x, base_y - height, bar_width, height, QColor(color))
            painter.setPen(QColor("#334155"))
            painter.drawText(x, base_y + 4, bar_width, 20, Qt.AlignCenter, label)
            painter.drawText(x, max(2, base_y - height - 22), bar_width, 20, Qt.AlignCenter, str(value))


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("运行设置")
        form = QFormLayout(self)

        self.mode = QComboBox()
        self.mode.addItems(("自由模式", "定量模式", "定时模式"))
        if config.video_path is not None:
            self.mode.addItem("视频测试模式")
        self.mode.setCurrentText(config.mode)
        self.mode.setEnabled(config.video_path is None)
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 100000)
        self.quantity.setValue(config.target_quantity)
        self.duration = QSpinBox()
        self.duration.setRange(1, 1440)
        self.duration.setValue(config.duration_minutes)
        self.locator_conf = self._double_spin(config.locator_confidence)
        self.defect_threshold = self._double_spin(config.defect_threshold, decimals=6, step=0.01)
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.03, 5.0)
        self.interval.setDecimals(2)
        self.interval.setSingleStep(0.05)
        self.interval.setValue(config.inference_interval)
        self.profile = QComboBox()
        self.profile.addItems(IMPLEMENTED)
        current_profile = config.inference_profile if config.inference_profile in IMPLEMENTED else "FULL"
        self.profile.setCurrentText(current_profile)
        self.profile.currentTextChanged.connect(self._sync_interval_from_profile)
        self.camera = QSpinBox()
        self.camera.setRange(0, 32)
        self.camera.setValue(config.camera_index)
        self.serial_port = QLineEdit(config.serial_port)
        self.serial_baudrate = QSpinBox()
        self.serial_baudrate.setRange(300, 4000000)
        self.serial_baudrate.setValue(config.serial_baudrate)

        form.addRow("运行模式", self.mode)
        form.addRow("目标数量", self.quantity)
        form.addRow("运行时长（分钟）", self.duration)
        form.addRow("齿轮定位阈值", self.locator_conf)
        form.addRow("缺陷判定阈值", self.defect_threshold)
        form.addRow("推理档位", self.profile)
        form.addRow("推理间隔（秒）", self.interval)
        form.addRow("摄像头索引", self.camera)
        form.addRow("串口", self.serial_port)
        form.addRow("波特率", self.serial_baudrate)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _sync_interval_from_profile(self, name):
        interval = SPECS.get(name, {}).get("inference_interval")
        if interval is not None:
            self.interval.setValue(interval)

    @staticmethod
    def _double_spin(value, decimals=2, step=0.05):
        spin = QDoubleSpinBox()
        spin.setRange(0.01, 0.99)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def apply(self):
        self.config.mode = self.mode.currentText()
        self.config.target_quantity = self.quantity.value()
        self.config.duration_minutes = self.duration.value()
        self.config.locator_confidence = self.locator_conf.value()
        self.config.defect_threshold = self.defect_threshold.value()
        self.config.inference_interval = self.interval.value()
        return (
            self.profile.currentText(),
            self.camera.value(),
            self.serial_port.text().strip(),
            self.serial_baudrate.value(),
        )


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.frame_store = LatestFrame()
        self.stats = InspectionStats()
        self.worker = None
        self.started_at = None
        self.last_counted_at = 0.0
        self.serial_output = SerialOutput(config.serial_port, config.serial_baudrate)
        self.last_result = None
        self.scratch_errors = 0
        self.worker_failed = False
        self.control_server = None
        self.setWindowTitle("GearPro 齿轮视觉检测系统")
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)
        self._build_ui()
        source_started = self._start_source()
        self._start_control_api()
        if source_started and self.config.video_path is not None:
            QTimer.singleShot(0, self.start_inspection)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        header = QHBoxLayout()
        title = QLabel("GearPro 齿轮视觉检测")
        title.setObjectName("title")
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings)
        self.video_button = QPushButton("测试视频")
        self.video_button.clicked.connect(self.choose_video)
        self.camera_button = QPushButton("实时相机")
        self.camera_button.clicked.connect(self.use_camera)
        self.camera_button.setVisible(self.config.video_path is not None)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.camera_button)
        header.addWidget(self.video_button)
        header.addWidget(self.settings_button)
        layout.addLayout(header)

        counters = QGridLayout()
        self.total_value = self._counter(counters, 0, "已检测")
        self.good_value = self._counter(counters, 1, "合格")
        self.defective_value = self._counter(counters, 2, "不合格")
        layout.addLayout(counters)

        content = QHBoxLayout()
        self.camera_view = CameraView(self.config, self.frame_store)
        content.addWidget(self.camera_view, 3)

        side = QVBoxLayout()
        settings_group = QGroupBox("当前设置")
        settings_layout = QVBoxLayout(settings_group)
        self.settings_summary = QLabel()
        self.settings_summary.setWordWrap(True)
        settings_layout.addWidget(self.settings_summary)
        side.addWidget(settings_group)

        result_group = QGroupBox("检测结果")
        result_layout = QVBoxLayout(result_group)
        self.verdict_label = QLabel("等待开始")
        self.verdict_label.setAlignment(Qt.AlignCenter)
        self.verdict_label.setObjectName("verdict")
        self.result_details = QLabel()
        self.result_details.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.result_details.setWordWrap(True)
        self.result_details.setMaximumHeight(110)
        self.result_details.setStyleSheet("background:#f8fafc; padding:5px; border-radius:5px;")
        self.result_image = QLabel("等待检测画面")
        self.result_image.setAlignment(Qt.AlignCenter)
        self.result_image.setMinimumHeight(130)
        self.result_image.setStyleSheet("background:#111827; color:#94a3b8; border-radius:6px;")
        result_layout.addWidget(self.verdict_label)
        result_layout.addWidget(self.result_image, 2)
        result_layout.addWidget(self.result_details)
        side.addWidget(result_group)

        chart_group = QGroupBox("检测统计")
        chart_layout = QVBoxLayout(chart_group)
        self.chart = StatsChart()
        chart_layout.addWidget(self.chart)
        side.addWidget(chart_group, 1)
        content.addLayout(side, 2)
        layout.addLayout(content, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("正在初始化摄像头…")
        self.start_button = QPushButton("开始运行")
        self.start_button.setObjectName("startButton")
        self.start_button.clicked.connect(self.toggle_inspection)
        self.clear_button = QPushButton("清空统计")
        self.clear_button.clicked.connect(self.clear_stats)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.clear_button)
        footer.addWidget(self.start_button)
        layout.addLayout(footer)

        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self.camera_view.capture_frame)
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._refresh_preview)
        self.mode_timer = QTimer(self)
        self.mode_timer.timeout.connect(self._check_mode_limit)
        self.mode_timer.start(500)
        self._refresh_settings_summary()

    def _counter(self, grid, column, caption):
        frame = QFrame()
        frame.setObjectName("counterCard")
        box = QVBoxLayout(frame)
        value = QLabel("0")
        value.setAlignment(Qt.AlignCenter)
        value.setObjectName("counterValue")
        label = QLabel(caption)
        label.setAlignment(Qt.AlignCenter)
        box.addWidget(value)
        box.addWidget(label)
        grid.addWidget(frame, 0, column)
        return value

    def _preview_interval_ms(self):
        hz = max(1.0, float(self.config.ui_refresh_hz))
        return max(1, int(1000 / hz))

    def _refresh_preview(self):
        if self.config.video_path is not None:
            return
        packet = self.frame_store.read()
        if packet.frame is None:
            return
        self.camera_view.setPixmap(frame_to_pixmap(packet.frame, self.camera_view.size()))

    def _start_source(self):
        if self.config.video_path is not None:
            self.camera_timer.stop()
            self.preview_timer.stop()
            self.camera_view.stop()
            self.camera_view.setText(f"视频测试：{self.config.video_path.name}")
            self.status_label.setText("正在准备视频测试…")
            self.camera_button.setVisible(True)
            return True
        if self.camera_view.start():
            self.camera_timer.start(max(1, int(1000 / self.config.camera_fps)))
            self.preview_timer.start(self._preview_interval_ms())
            self.status_label.setText("摄像头已连接")
            self.camera_button.setVisible(False)
            return True
        self.camera_timer.stop()
        self.preview_timer.stop()
        self.status_label.setText(self.camera_view.error_message or "摄像头连接失败，请检查设置和设备")
        return False

    def toggle_inspection(self):
        if self.worker is not None and self.worker.isRunning():
            self.stop_inspection()
        else:
            self.start_inspection()

    def start_inspection(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if self.config.inference_profile == "SAFE_STOP":
            apply_to_config(self.config, "FULL")
            self._refresh_settings_summary()
        if self.config.video_path is None and self.camera_view.capture is None:
            self.status_label.setText("无法开始：摄像头未连接")
            return
        if self.config.video_path is not None and not self.config.video_path.is_file():
            self.status_label.setText(f"无法开始：找不到视频 {self.config.video_path}")
            return
        self.worker = InspectionThread(self.config, self.frame_store, self)
        self.worker.result_ready.connect(self.show_result)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.failed.connect(self.show_failure)
        self.worker.finished.connect(self._worker_finished)
        self.started_at = time.monotonic()
        self.last_counted_at = 0.0
        self.worker_failed = False
        self.start_button.setText("停止运行")
        self.settings_button.setEnabled(False)
        self.video_button.setEnabled(False)
        self.camera_button.setEnabled(False)
        self.worker.start()

    def set_inference_profile(self, name):
        try:
            plan = apply_to_config(self.config, name)
        except ProfileError as exc:
            return False, str(exc)
        if plan["stop_worker"]:
            self.stop_inspection()
        elif plan["start_worker"]:
            self.start_inspection()
        self._refresh_settings_summary()
        return True, f"已切换到 {name}"

    def stop_inspection(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(2000)
        self._worker_finished()

    def _worker_finished(self):
        self.start_button.setText("开始运行")
        self.settings_button.setEnabled(True)
        self.video_button.setEnabled(True)
        self.camera_button.setEnabled(True)

    def show_result(self, result):
        self.last_result = result
        self.result_image.setPixmap(frame_to_pixmap(result.annotated_frame, self.result_image.size()))
        if self.config.video_path is not None:
            self.camera_view.setPixmap(frame_to_pixmap(result.annotated_frame, self.camera_view.size()))
        self.verdict_label.setText(result.verdict)
        state = "idle" if not result.has_gear else ("bad" if result.is_defective else "good")
        self.verdict_label.setProperty("state", state)
        self.verdict_label.style().unpolish(self.verdict_label)
        self.verdict_label.style().polish(self.verdict_label)
        lines = [
            f"模型：{result.model_version or '未知'}，推理耗时：{result.elapsed_ms:.1f} ms",
            (
                f"定位 {result.locator_latency_ms:.1f} ms，"
                f"分类 {result.classifier1_latency_ms:.1f}+{result.classifier2_latency_ms:.1f} ms，"
                f"检测 {result.detector_latency_ms:.1f} ms"
            ),
            f"定位数量：{len(result.observations)}",
        ]
        for index, item in enumerate(result.observations, 1):
            lines.append(
                f"齿轮 {index}：定位 {item.location_confidence:.1%}，缺陷 {item.defect_score:.1%}，"
                f"分类 {item.classifier_probability:.1%}，检测 {item.detector_probability:.1%}"
            )
        self.result_details.setText("\n".join(lines))

        now = time.monotonic()
        if result.has_gear and now - self.last_counted_at >= self.config.result_cooldown:
            self.last_counted_at = now
            self.stats.add(result.is_defective)
            self._refresh_stats()
            if self.config.serial_enabled:
                _ok, message = self.serial_output.send_verdict(result.is_defective)
                self.status_label.setText(message)
            self._check_mode_limit()

    def show_failure(self, message):
        self.scratch_errors += 1
        self.worker_failed = True
        self.status_label.setText("检测错误：" + message)
        self.result_details.setText(message)

    def current_snapshot(self):
        worker_running = self.worker is not None and self.worker.isRunning()
        return build_snapshot(
            self.config,
            self.frame_store,
            self.camera_view.opened,
            self.camera_view.device_path,
            self.camera_view.read_failures,
            self.camera_view.actual_fps,
            self.serial_output,
            last_result=self.last_result,
            inspection_active=worker_running,
            scratch_errors=self.scratch_errors,
        )

    def control_extras(self):
        return {
            "worker_failed": bool(self.worker_failed),
            "serial_enabled": bool(self.config.serial_enabled),
            "serial_open": bool(self.serial_output.is_open),
            "video_mode": self.config.video_path is not None,
        }

    def _restart_camera(self):
        self.camera_timer.stop()
        self.preview_timer.stop()
        self.camera_view.stop()
        return self._start_source()

    def execute_action(self, name, params):
        if name == "restart_camera":
            token = {"camera_index": self.config.camera_index}
            if not self._restart_camera():
                raise RuntimeError(self.camera_view.error_message or "摄像头重启失败")
            return token
        if name == "restart_worker":
            self.stop_inspection()
            self.start_inspection()
            if self.worker is None or not self.worker.isRunning():
                raise RuntimeError(self.status_label.text() or "worker 启动失败")
            return {}
        if name == "reconnect_serial":
            token = {"port": self.config.serial_port, "baudrate": self.config.serial_baudrate}
            self.serial_output.reconfigure(self.config.serial_port, self.config.serial_baudrate)
            ok, error = self.serial_output.ensure_open()
            if not ok:
                raise RuntimeError(error or "串口打开失败")
            return token
        if name == "set_inference_profile":
            previous = self.config.inference_profile
            ok, message = self.set_inference_profile(params.get("profile"))
            if not ok:
                raise RuntimeError(message)
            return {"previous": previous}
        if name == "pause_inspection":
            self.stop_inspection()
            return {}
        if name == "resume_inspection":
            self.start_inspection()
            if self.worker is None or not self.worker.isRunning():
                raise RuntimeError(self.status_label.text() or "检测未能恢复")
            return {}
        raise RuntimeError(f"动作 {name} 没有执行器")

    def rollback_action(self, name, token):
        token = token or {}
        if name == "restart_camera":
            self._restart_camera()
            return
        if name == "restart_worker":
            self.stop_inspection()
            return
        if name == "reconnect_serial":
            self.serial_output.close()
            return
        if name == "set_inference_profile":
            previous = token.get("previous")
            if previous:
                self.set_inference_profile(previous)
            return
        if name == "pause_inspection":
            self.start_inspection()
            return
        if name == "resume_inspection":
            self.stop_inspection()

    def _start_control_api(self):
        port = int(getattr(self.config, "control_port", 8787) or 0)
        host = getattr(self.config, "control_host", "127.0.0.1")
        if not port:
            return
        from .control import start_control_api

        try:
            self.control_server = start_control_api(self, host=host, port=port)
        except OSError as exc:
            self.control_server = None
            print(f"Control API 未能监听 {host}:{port}：{exc}")

    def choose_video(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择测试视频",
            "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.m4v);;所有文件 (*)",
        )
        if not path:
            return
        self.stop_inspection()
        self.camera_timer.stop()
        self.preview_timer.stop()
        self.camera_view.stop()
        self.config.video_path = Path(path).resolve()
        self.config.mode = "视频测试模式"
        self.config.serial_enabled = False
        self._refresh_settings_summary()
        if self._start_source():
            self.start_inspection()

    def use_camera(self):
        self.stop_inspection()
        self.config.video_path = None
        self.config.mode = "自由模式"
        self.config.serial_enabled = True
        self.camera_view.clear()
        self._refresh_settings_summary()
        self._start_source()

    def clear_stats(self):
        self.stats.clear()
        self._refresh_stats()
        self.result_details.clear()
        self.verdict_label.setText("等待检测")

    def _refresh_stats(self):
        self.total_value.setText(str(self.stats.total))
        self.good_value.setText(str(self.stats.good))
        self.defective_value.setText(str(self.stats.defective))
        self.chart.set_stats(self.stats)

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        profile_name, new_camera_index, serial_port, serial_baudrate = dialog.apply()
        ok, message = self.set_inference_profile(profile_name)
        if not ok:
            self.status_label.setText(message)
        if new_camera_index != self.config.camera_index:
            self.camera_timer.stop()
            self.preview_timer.stop()
            self.camera_view.stop()
            self.config.camera_index = new_camera_index
            self._start_source()
        if (serial_port, serial_baudrate) != (self.config.serial_port, self.config.serial_baudrate):
            self.config.serial_port = serial_port
            self.config.serial_baudrate = serial_baudrate
            self.serial_output.reconfigure(serial_port, serial_baudrate)
        self._refresh_settings_summary()

    def _refresh_settings_summary(self):
        details = [
            f"模式：{self.config.mode}",
            f"模型 1：{self.config.locator_model.name}（齿轮定位）",
            f"模型 2：{self.config.model2_config.parent.name}（Scratch V5 融合）",
            f"定位阈值：{self.config.locator_confidence:.2f}",
            f"缺陷阈值：{self.config.defect_threshold:.6f}",
            f"推理档位：{self.config.inference_profile}",
            f"推理间隔：{self.config.inference_interval:.2f} 秒",
            (
                "串口：已禁用（视频测试）"
                if not self.config.serial_enabled
                else f"串口：{self.config.serial_port} @ {self.config.serial_baudrate}"
            ),
        ]
        if self.config.video_path is not None:
            details.append(f"测试视频：{self.config.video_path.name}")
        if self.config.mode == "定量模式":
            details.append(f"目标数量：{self.config.target_quantity}")
        elif self.config.mode == "定时模式":
            details.append(f"运行时长：{self.config.duration_minutes} 分钟")
        self.settings_summary.setText("\n".join(details))

    def _check_mode_limit(self):
        self._guardian_tick()
        if self.worker is None or not self.worker.isRunning():
            return
        quantity_done = self.config.mode == "定量模式" and self.stats.total >= self.config.target_quantity
        time_done = (
            self.config.mode == "定时模式"
            and self.started_at is not None
            and time.monotonic() - self.started_at >= self.config.duration_minutes * 60
        )
        if quantity_done or time_done:
            self.status_label.setText("当前任务已完成")
            QTimer.singleShot(0, self.stop_inspection)

    def _guardian_tick(self):
        snapshot = self.current_snapshot()
        if thermal_stop_needed(snapshot, self.config.inference_profile):
            self.set_inference_profile("SAFE_STOP")
            self.status_label.setText("Guardian：温度过高，已切换 SAFE_STOP")

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait()
        self.camera_timer.stop()
        self.preview_timer.stop()
        self.camera_view.stop()
        self.serial_output.close()
        if self.control_server is not None:
            self.control_server.shutdown()
            self.control_server.server_close()
            self.control_server = None
        event.accept()


APP_STYLE = """
QMainWindow { background: #f1f5f9; color: #0f172a; }
QLabel#title { font-size: 25px; font-weight: 700; padding: 8px; }
QFrame#counterCard, QGroupBox { background: white; border: 1px solid #dbe3ee; border-radius: 8px; }
QGroupBox { margin-top: 10px; padding-top: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLabel#counterValue { font-size: 30px; font-weight: 700; color: #2563eb; }
QLabel#verdict { font-size: 24px; font-weight: 700; padding: 10px; border-radius: 6px; }
QLabel#verdict[state="good"] { color: #15803d; background: #dcfce7; }
QLabel#verdict[state="bad"] { color: #b91c1c; background: #fee2e2; }
QPushButton { padding: 8px 18px; border: 0; border-radius: 6px; background: #e2e8f0; }
QPushButton:hover { background: #cbd5e1; }
QPushButton#startButton { background: #2563eb; color: white; font-weight: 700; min-width: 110px; }
QPushButton#startButton:hover { background: #1d4ed8; }
"""
