"""Headless GearPro lifecycle and shared application state."""

from dataclasses import asdict
from pathlib import Path
import shutil
import threading
import time

import cv2

from .camera import CameraCapture
from .config import RUNTIME_ROOT
from .frames import LatestFrame
from .serial_io import SerialOutput
from .telemetry import build_snapshot
from .types import InspectionStats
from .worker import InspectionWorker


class GearProRuntime:
    def __init__(self, config):
        self.config = config
        self.raw_frames = LatestFrame()
        self.annotated_frames = LatestFrame()
        self.camera = CameraCapture(config, self.raw_frames)
        self.serial = SerialOutput(config.serial_port, config.serial_baudrate)
        self.stats = InspectionStats()
        self.last_result = None
        self.status = "正在初始化"
        self.error = None
        self.error_count = 0
        self.started_at = None
        self._last_counted_at = 0.0
        self._managed_video = None
        self._lock = threading.RLock()
        self._jpeg_lock = threading.Lock()
        self._jpeg_cache = {}
        self.control_server = None
        self._guardian_stop = threading.Event()
        self._guardian_thread = None
        self.worker = InspectionWorker(
            config,
            self.raw_frames,
            self._on_result,
            self._on_status,
            self._on_error,
            self._on_video_complete,
        )

    def startup(self):
        self.worker.start_service()
        if self.config.video_path is not None:
            self.config.serial_enabled = False
            self.status = "正在准备视频测试…"
            self.start_inspection()
        elif self.camera.start():
            self.status = "摄像头已连接"
        else:
            self.status = self.camera.error_message or "摄像头连接失败"
        self._start_control_api()
        self._start_guardian()

    def shutdown(self):
        self._guardian_stop.set()
        if self._guardian_thread is not None:
            self._guardian_thread.join(timeout=1.0)
            self._guardian_thread = None
        if self.control_server is not None:
            self.control_server.shutdown()
            self.control_server.server_close()
            self.control_server = None
        self.worker.stop_service()
        self.camera.stop()
        self.serial.close()
        self._cleanup_managed_video()

    @property
    def inspection_active(self):
        return self.worker.active

    @property
    def source(self):
        return "video" if self.config.video_path is not None else "camera"

    def start_inspection(self):
        if self.config.inference_profile == "SAFE_STOP":
            raise RuntimeError("SAFE_STOP 档位下不能开始检测")
        if self.config.video_path is None and not self.camera.opened:
            raise RuntimeError(self.camera.error_message or "摄像头未连接")
        if self.config.video_path is not None and not self.config.video_path.is_file():
            raise RuntimeError(f"找不到视频：{self.config.video_path}")
        with self._lock:
            self.error = None
            self.started_at = time.monotonic()
            self.status = "正在启动检测…"
        self.worker.start_inspection()

    def stop_inspection(self, status="检测已停止"):
        self.worker.pause()
        with self._lock:
            self.status = status

    def use_camera(self):
        self.stop_inspection()
        self.config.video_path = None
        self.config.mode = "自由模式"
        self.config.serial_enabled = True
        self.raw_frames.clear()
        self.annotated_frames.clear()
        self._cleanup_managed_video()
        if not self.camera.restart():
            raise RuntimeError(self.camera.error_message or "摄像头连接失败")
        self.status = "摄像头已连接"

    def use_video(self, path, managed=False):
        path = Path(path).resolve()
        capture = cv2.VideoCapture(str(path))
        readable = capture.isOpened()
        capture.release()
        if not readable:
            if managed:
                path.unlink(missing_ok=True)
            raise ValueError("无法读取该视频文件")
        self.stop_inspection()
        self.camera.stop()
        self._cleanup_managed_video()
        self.raw_frames.clear()
        self.annotated_frames.clear()
        self.config.video_path = path
        self.config.mode = "视频测试模式"
        self.config.serial_enabled = False
        self._managed_video = path if managed else None
        self.start_inspection()

    def reset_stats(self):
        with self._lock:
            self.stats.clear()
            self.last_result = None
            self.annotated_frames.clear()

    def update_settings(self, values):
        camera_fields = {"camera_index", "camera_width", "camera_height", "camera_fps"}
        serial_fields = {"serial_port", "serial_baudrate"}
        old_camera = tuple(getattr(self.config, name) for name in sorted(camera_fields))
        old_serial = (self.config.serial_port, self.config.serial_baudrate)
        previous_profile = self.config.inference_profile
        profile = values.get("inference_profile")
        self.config.update(values)
        self.config.persist()
        new_camera = tuple(getattr(self.config, name) for name in sorted(camera_fields))
        if self.source == "camera" and old_camera != new_camera:
            if not self.camera.restart():
                raise RuntimeError(self.camera.error_message or "摄像头重新连接失败")
        if serial_fields.intersection(values) and old_serial != (
            self.config.serial_port,
            self.config.serial_baudrate,
        ):
            self.serial.reconfigure(self.config.serial_port, self.config.serial_baudrate)
        if profile == "SAFE_STOP":
            self.stop_inspection("已进入 SAFE_STOP")
        elif previous_profile == "SAFE_STOP" and profile is not None:
            self.start_inspection()

    def state(self, control=None):
        with self._lock:
            result = self.last_result
            stats = asdict(self.stats)
            status = self.status
            error = self.error
            started_at = self.started_at
        snapshot = build_snapshot(
            self.config,
            self.raw_frames,
            self.camera.opened if self.source == "camera" else True,
            self.camera.device_path if self.source == "camera" else str(self.config.video_path),
            self.camera.read_failures if self.source == "camera" else 0,
            self.camera.actual_fps if self.source == "camera" else 0.0,
            self.serial,
            last_result=result,
            inspection_active=self.inspection_active,
            scratch_errors=self.error_count,
        )
        stats["good_rate"] = 0.0 if not stats["total"] else stats["good"] / stats["total"]
        return {
            "version": "api.v1",
            "status": status,
            "error": error,
            "source": {
                "type": self.source,
                "video_name": None if self.config.video_path is None else self.config.video_path.name,
            },
            "inspection": {
                "active": self.inspection_active,
                "started_seconds_ago": None if started_at is None else max(0.0, time.monotonic() - started_at),
                "model_loaded": self.worker.model_loaded,
            },
            "stats": stats,
            "result": self._serialize_result(result),
            "settings": self.settings(),
            "health": snapshot,
            "control": control or {},
        }

    def current_snapshot(self):
        return self.state()["health"]

    def control_extras(self):
        return {
            "worker_failed": self.error is not None,
            "serial_enabled": bool(self.config.serial_enabled),
            "serial_open": bool(self.serial.is_open),
            "video_mode": self.config.video_path is not None,
        }

    def set_inference_profile(self, name):
        from .profiles import ProfileError, apply_to_config

        try:
            plan = apply_to_config(self.config, name)
        except ProfileError as exc:
            return False, str(exc)
        try:
            self.config.persist()
        except OSError:
            pass
        if plan["stop_worker"]:
            self.stop_inspection("已进入 SAFE_STOP")
        elif plan["start_worker"]:
            self.start_inspection()
        return True, f"已切换到 {name}"

    def execute_action(self, name, params):
        if name == "restart_camera":
            if self.source != "camera":
                raise RuntimeError("视频模式下不能重启摄像头")
            if not self.camera.restart():
                raise RuntimeError(self.camera.error_message or "摄像头重启失败")
            return {"camera_index": self.config.camera_index}
        if name == "restart_worker":
            self.stop_inspection()
            self.start_inspection()
            return {}
        if name == "reconnect_serial":
            token = {"port": self.config.serial_port, "baudrate": self.config.serial_baudrate}
            self.serial.reconfigure(self.config.serial_port, self.config.serial_baudrate)
            ok, error = self.serial.ensure_open()
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
            return {}
        raise RuntimeError(f"动作 {name} 没有执行器")

    def rollback_action(self, name, token):
        token = token or {}
        if name == "restart_camera":
            self.camera.restart()
            return
        if name == "restart_worker":
            self.stop_inspection()
            return
        if name == "reconnect_serial":
            self.serial.close()
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

    def _start_guardian(self):
        from .guardian import thermal_stop_needed

        def loop():
            while not self._guardian_stop.wait(0.5):
                snapshot = self.current_snapshot()
                if thermal_stop_needed(snapshot, self.config.inference_profile):
                    self.set_inference_profile("SAFE_STOP")
                    with self._lock:
                        self.status = "Guardian：温度过高，已切换 SAFE_STOP"

        self._guardian_stop.clear()
        self._guardian_thread = threading.Thread(target=loop, name="gearpro-guardian", daemon=True)
        self._guardian_thread.start()

    def settings(self):
        return {
            "mode": self.config.mode,
            "target_quantity": self.config.target_quantity,
            "duration_minutes": self.config.duration_minutes,
            "locator_confidence": self.config.locator_confidence,
            "defect_threshold": self.config.defect_threshold,
            "inference_profile": self.config.inference_profile,
            "inference_interval": self.config.inference_interval,
            "camera_index": self.config.camera_index,
            "camera_width": self.config.camera_width,
            "camera_height": self.config.camera_height,
            "camera_fps": self.config.camera_fps,
            "serial_port": self.config.serial_port,
            "serial_baudrate": self.config.serial_baudrate,
            "stream_fps": self.config.stream_fps,
            "stream_quality": self.config.stream_quality,
        }

    def jpeg(self, view="auto"):
        if view not in ("auto", "raw", "annotated"):
            raise ValueError("view 必须是 auto、raw 或 annotated")
        selected = view
        if selected == "auto":
            selected = "annotated" if self.inspection_active and self.last_result is not None else "raw"
        store = self.annotated_frames if selected == "annotated" else self.raw_frames
        packet = store.read()
        if packet.frame is None and selected == "annotated":
            packet = self.raw_frames.read()
            selected = "raw"
        if packet.frame is None:
            return None
        now = time.monotonic()
        minimum_period = 1.0 / max(1.0, float(self.config.stream_fps))
        with self._jpeg_lock:
            cached = self._jpeg_cache.get(selected)
            if cached and cached[0] == packet.sequence:
                return cached[2]
            if cached and now - cached[1] < minimum_period:
                return cached[2]
            ok, encoded = cv2.imencode(
                ".jpg",
                packet.frame,
                [cv2.IMWRITE_JPEG_QUALITY, int(self.config.stream_quality)],
            )
            if not ok:
                return None
            data = encoded.tobytes()
            self._jpeg_cache[selected] = (packet.sequence, now, data)
            return data

    def _on_result(self, result):
        now = time.monotonic()
        self.annotated_frames.publish(result.annotated_frame)
        with self._lock:
            self.last_result = result
            self.error = None
            if result.has_gear and now - getattr(self, "_last_counted_at", 0.0) >= self.config.result_cooldown:
                self._last_counted_at = now
                self.stats.add(result.is_defective)
                if self.config.serial_enabled:
                    _ok, message = self.serial.send_verdict(result.is_defective)
                    self.status = message
            quantity_done = self.config.mode == "定量模式" and self.stats.total >= self.config.target_quantity
            time_done = (
                self.config.mode == "定时模式"
                and self.started_at is not None
                and now - self.started_at >= self.config.duration_minutes * 60
            )
        if quantity_done or time_done:
            self.stop_inspection("当前任务已完成")

    def _on_status(self, message):
        with self._lock:
            self.status = message

    def _on_error(self, message):
        with self._lock:
            self.error_count += 1
            self.error = message
            self.status = "检测错误"

    def _on_video_complete(self, path):
        del path

    def _cleanup_managed_video(self):
        path = self._managed_video
        self._managed_video = None
        if path is not None:
            path.unlink(missing_ok=True)
        uploads = RUNTIME_ROOT / "uploads"
        if uploads.is_dir() and not any(uploads.iterdir()):
            shutil.rmtree(uploads, ignore_errors=True)

    @staticmethod
    def _serialize_result(result):
        if result is None:
            return None
        return {
            "verdict": result.verdict,
            "has_gear": result.has_gear,
            "is_defective": result.is_defective,
            "model_version": result.model_version,
            "elapsed_ms": result.elapsed_ms,
            "locator_latency_ms": result.locator_latency_ms,
            "classifier1_latency_ms": result.classifier1_latency_ms,
            "classifier2_latency_ms": result.classifier2_latency_ms,
            "detector_latency_ms": result.detector_latency_ms,
            "fusion_latency_ms": result.fusion_latency_ms,
            "observations": [asdict(item) for item in result.observations],
        }
