"""Headless GearPro lifecycle and shared application state."""

from collections import deque
from dataclasses import asdict
from pathlib import Path
import shutil
import threading
import time
import uuid

import cv2

from .camera import CameraCapture
from .config import PERSISTED_FIELDS, RUNTIME_ROOT, load_last_known_good_snapshot
from .control_view import as_control_view
from .frames import LatestFrame
from .guardian import thermal_stop_needed
from .serial_io import SerialOutput
from .telemetry import build_snapshot, camera_health, locator_backend
from .types import InspectionStats
from .verify import summarize_cycles
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
        self._action_lock = threading.Lock()
        self._emergency_hold = False
        self._config_backup = None
        self._action_cycles = deque(maxlen=64)
        self._window_started = None
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
        if self._emergency_hold:
            raise RuntimeError("紧急停机锁存中，不能开始检测")
        if self.config.inference_profile == "SAFE_STOP":
            raise RuntimeError("SAFE_STOP 档位下不能开始检测")
        if thermal_stop_needed(self.current_snapshot(), "FULL"):
            raise RuntimeError("温度保护仍有效，不能开始检测")
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
        values = dict(values)
        profile = values.pop("inference_profile", None)
        camera_fields = {"camera_index", "camera_width", "camera_height", "camera_fps"}
        serial_fields = {"serial_port", "serial_baudrate"}
        old_camera = tuple(getattr(self.config, name) for name in sorted(camera_fields))
        old_serial = (self.config.serial_port, self.config.serial_baudrate)
        if values:
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
        if profile is not None:
            ok, message = self.set_inference_profile(profile)
            if not ok:
                raise RuntimeError(message)

    def state(self, control=None, api_version="api.v2"):
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
            schema_version="system-snapshot.v1" if api_version == "api.v1" else "system-snapshot.v2",
        )
        stats["good_rate"] = 0.0 if not stats["total"] else stats["good"] / stats["total"]
        return {
            "version": api_version,
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
            "result": self._serialize_result_v1(result) if api_version == "api.v1" else self._serialize_result_v2(result),
            "settings": self.settings(api_version),
            "health": snapshot,
            "control": control or {},
        }

    def settings(self, api_version="api.v2"):
        settings = {
            "mode": self.config.mode,
            "target_quantity": self.config.target_quantity,
            "duration_minutes": self.config.duration_minutes,
            "locator_confidence": self.config.locator_confidence,
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
        if api_version == "api.v1":
            settings["defect_threshold"] = self.config.scratch_threshold
        else:
            settings.update({
                "scratch_threshold": self.config.scratch_threshold,
                "missing_hole_threshold": self.config.missing_hole_threshold,
                "model_default_thresholds": {
                    "scratch": self.config.scratch_model_default_threshold,
                    "missing_hole": self.config.missing_hole_model_default_threshold,
                },
            })
        return settings

    def current_snapshot(self):
        health = self.state(api_version="api.v2")["health"]
        return as_control_view(health)

    def control_extras(self):
        backup = self._effective_config_backup() or {}
        packet = self.raw_frames.read()
        with self._lock:
            cycles = list(self._action_cycles)
            failed = self.error is not None
            profile = self.config.inference_profile
            hold = self._emergency_hold
        snapshot = self.current_snapshot()
        return {
            "serial_enabled": bool(self.config.serial_enabled),
            "serial_open": bool(self.serial.is_open),
            "video_mode": self.config.video_path is not None,
            "replay_mode": self.config.replay_dir is not None,
            "config_backup": bool(backup),
            "models_ok": True,
            "config_profile": profile,
            "backup_profile": backup.get("inference_profile"),
            "backup_backend": locator_backend(backup["locator_model"]) if backup.get("locator_model") else None,
            "inspection_should_run": self.inspection_active,
            "inspection_can_run": self.inspection_active,
            "window_stats": summarize_cycles(cycles),
            "window_elapsed_s": 0.0 if self._window_started is None else max(0.0, time.monotonic() - self._window_started),
            "camera_health": camera_health(
                True if self.source == "video" else self.camera.opened,
                None if packet is None else packet.age_ms,
                0 if self.source == "video" else self.camera.read_failures,
            ),
            "critical_incident": failed,
            "worker_failed": failed,
            "settings": self.settings(),
            "emergency_hold": hold,
            "thermal_stop_needed": thermal_stop_needed(snapshot, profile),
            "authority": None,
        }

    def begin_verify_window(self):
        self._action_cycles.clear()
        self._window_started = time.monotonic()

    def promote_last_known_good(self):
        self.config.persist_last_known_good()

    def _effective_config_backup(self):
        if self._config_backup:
            return self._config_backup
        return load_last_known_good_snapshot()

    def human_action(self, name, params=None):
        from .control import ControlService

        return ControlService(self).run_action(
            {
                "name": name,
                "params": params or {},
                "source": "human",
                "request_id": f"web-{uuid.uuid4().hex}",
            },
            authority="human",
        )

    def _remember_config(self):
        self._config_backup = {
            "locator_model": str(self.config.locator_model),
            "fields": {name: getattr(self.config, name) for name in PERSISTED_FIELDS},
            "inference_profile": self.config.inference_profile,
            "inspection_active": self.inspection_active,
        }

    def rebuild_inspector(self, resume=True):
        self.stop_inspection("正在重建定位与双专项模型…")
        self.worker.drop_inspector()
        self.config.validate_models()
        if not resume or self.config.inference_profile == "SAFE_STOP":
            return
        with self._lock:
            self.error = None
        self.start_inspection()
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            if self.worker.model_loaded and self.error is None:
                return
            if self.error:
                raise RuntimeError(self.error)
            time.sleep(0.2)
        raise RuntimeError("inspector 重建超时")

    def _restore_config_backup(self, snap):
        previous_locator = Path(self.config.locator_model)
        self.config.update(snap["fields"])
        self.config.locator_model = Path(snap["locator_model"])
        rebuild = previous_locator.resolve() != Path(self.config.locator_model).resolve()
        want_run = bool(snap.get("inspection_active")) and self.config.inference_profile != "SAFE_STOP"
        if rebuild:
            self.rebuild_inspector(resume=want_run)
        elif self.config.inference_profile == "SAFE_STOP":
            self.stop_inspection("已进入 SAFE_STOP")
        elif want_run and not self.inspection_active:
            self.start_inspection()
        try:
            self.config.persist()
        except OSError:
            pass

    def set_inference_profile(self, name):
        from .profiles import ProfileError, apply_to_config

        previous = self.config.inference_profile
        was_active = self.inspection_active
        try:
            plan = apply_to_config(self.config, name)
        except ProfileError as exc:
            return False, str(exc)
        if name != "SAFE_STOP" and self._emergency_hold:
            if thermal_stop_needed(self.current_snapshot(), "FULL"):
                apply_to_config(self.config, previous)
                return False, "紧急停机锁存中，拒绝离开 SAFE_STOP"
            self._emergency_hold = False
        try:
            self.config.persist()
        except OSError:
            pass
        try:
            if plan["stop_worker"]:
                self.stop_inspection("已进入 SAFE_STOP")
            elif plan["start_worker"]:
                self.start_inspection()
            elif was_active and name != "SAFE_STOP" and not self.inspection_active:
                self.start_inspection()
        except Exception:
            try:
                apply_to_config(self.config, previous)
            except Exception:
                pass
            raise
        return True, f"已切换到 {name}"

    def set_locator_profile(self, name):
        from .profiles import locator_path_for

        path = locator_path_for(name)
        previous = str(self.config.locator_model)
        was_active = self.inspection_active
        self.config.locator_model = path
        try:
            self.config.persist()
        except OSError:
            pass
        resume = was_active and self.config.inference_profile != "SAFE_STOP"
        self.rebuild_inspector(resume=resume)
        return {"previous_locator": previous}

    def reload_persisted_config(self):
        from .profiles import ProfileError, apply_to_config

        was_active = self.inspection_active
        self.config.load_persisted()
        try:
            plan = apply_to_config(self.config, self.config.inference_profile)
        except ProfileError as exc:
            raise RuntimeError(str(exc)) from exc
        self.config.validate_models()
        resume = (not plan["stop_worker"]) and (was_active or plan["start_worker"])
        if plan["stop_worker"]:
            self.stop_inspection("已进入 SAFE_STOP")
        elif resume and not self.inspection_active:
            self.start_inspection()
        return {}

    def execute_action(self, name, params):
        with self._action_lock:
            return self._execute_action_locked(name, params)

    def _execute_action_locked(self, name, params):
        params = params or {}
        if name != "get_state":
            self.begin_verify_window()
        if name in ("set_inference_profile", "set_locator_profile", "reload_config", "apply_settings"):
            self._remember_config()
        if name == "restart_camera":
            if self.source != "camera":
                raise RuntimeError("视频模式下不能重启摄像头")
            if not self.camera.restart():
                raise RuntimeError(self.camera.error_message or "摄像头重启失败")
            return {"camera_index": self.config.camera_index}
        if name == "restart_worker":
            self.rebuild_inspector(resume=self.config.inference_profile != "SAFE_STOP")
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
        if name == "set_locator_profile":
            return self.set_locator_profile(params.get("profile"))
        if name == "reload_config":
            return self.reload_persisted_config()
        if name == "rollback_config":
            snap = self._effective_config_backup()
            if not snap:
                raise RuntimeError("没有可回滚的配置快照")
            self._restore_config_backup(snap)
            return {}
        if name == "apply_settings":
            self.update_settings(params or {})
            return {"applied": sorted((params or {}).keys())}
        if name == "use_camera":
            self.use_camera()
            return {}
        if name == "use_video":
            path = Path(params.get("path"))
            self.use_video(path, bool(params.get("managed")))
            return {}
        if name == "reset_stats":
            self.reset_stats()
            return {}
        if name == "pause_inspection":
            self.stop_inspection()
            return {}
        if name == "resume_inspection":
            self.start_inspection()
            return {}
        if name == "get_state":
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
        if name == "set_locator_profile":
            previous = token.get("previous_locator")
            if previous:
                self.config.locator_model = Path(previous)
                self.rebuild_inspector(resume=self.config.inference_profile != "SAFE_STOP")
            return

    def _start_control_api(self):
        port = int(getattr(self.config, "control_port", 8787) or 0)
        host = getattr(self.config, "control_host", "127.0.0.1")
        if not port:
            return
        from .control import start_control_api

        try:
            self.control_server = start_control_api(self, host=host, port=port)
        except Exception as exc:
            self.control_server = None
            print(f"Control API 未能监听 {host}:{port}：{exc}")

    def _start_guardian(self):
        def loop():
            while not self._guardian_stop.wait(0.5):
                try:
                    snapshot = self.current_snapshot()
                    if thermal_stop_needed(snapshot, self.config.inference_profile):
                        self._emergency_hold = True
                        ok, message = self.set_inference_profile("SAFE_STOP")
                        if ok:
                            with self._lock:
                                self.status = "Guardian：温度过高，已切换 SAFE_STOP"
                        else:
                            self.stop_inspection(message or "Guardian：温度过高")
                except Exception:
                    continue

        self._guardian_stop.clear()
        self._guardian_thread = threading.Thread(target=loop, name="gearpro-guardian", daemon=True)
        self._guardian_thread.start()

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
            self._action_cycles.append(
                {
                    "valid": bool(result.has_gear),
                    "locator_ms": result.locator_latency_ms,
                    "v5_ms": result.scratch_latency_ms,
                    "elapsed_ms": result.elapsed_ms,
                }
            )
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
    def _serialize_result_v1(result):
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
            "observations": [
                {
                    "box": item.box,
                    "location_confidence": item.location_confidence,
                    "defect_score": item.defect_score,
                    "classifier_probability": item.classifier_probability,
                    "detector_probability": item.detector_probability,
                    "auxiliary_box": item.auxiliary_box,
                }
                for item in result.observations
            ],
            "compatibility_notice": "v1 probability fields describe Scratch V5; verdict includes both specialists",
        }

    @staticmethod
    def _serialize_result_v2(result):
        if result is None:
            return None
        observations = []
        for item in result.observations:
            observations.append({
                "box": item.box,
                "location_confidence": item.location_confidence,
                "is_defective": item.is_defective,
                "reject_reasons": item.reject_reasons,
                "specialists": {
                    "scratch": {
                        "version": result.model_version,
                        "probability": item.defect_score,
                        "threshold": item.scratch_threshold,
                        "reject": item.scratch_is_reject,
                        "classifier_probability": item.classifier_probability,
                        "detector_probability": item.detector_probability,
                        "auxiliary_box": item.auxiliary_box,
                    },
                    "missing_hole": {
                        "version": result.missing_hole_model_version,
                        "probability": item.missing_hole_probability,
                        "threshold": item.missing_hole_threshold,
                        "reject": item.missing_hole_reject,
                        "classifier_probability": item.missing_hole_classifier_probability,
                        "detector_probability": item.missing_hole_detector_probability,
                        "auxiliary_box": item.missing_hole_auxiliary_box,
                    },
                },
            })
        return {
            "verdict": result.verdict,
            "has_gear": result.has_gear,
            "is_defective": result.is_defective,
            "reject_reasons": result.reject_reasons,
            "model_versions": {
                "scratch": result.model_version,
                "missing_hole": result.missing_hole_model_version,
            },
            "elapsed_ms": result.elapsed_ms,
            "timings": {
                "locator_ms": result.locator_latency_ms,
                "scratch": {
                    "classifier1_ms": result.classifier1_latency_ms,
                    "classifier2_ms": result.classifier2_latency_ms,
                    "detector_ms": result.detector_latency_ms,
                    "fusion_ms": result.fusion_latency_ms,
                    "total_ms": result.scratch_latency_ms,
                },
                "missing_hole": {
                    "classifier1_ms": result.missing_hole_classifier1_latency_ms,
                    "classifier2_ms": result.missing_hole_classifier2_latency_ms,
                    "detector_ms": result.missing_hole_detector_latency_ms,
                    "fusion_ms": result.missing_hole_fusion_latency_ms,
                    "total_ms": result.missing_hole_latency_ms,
                },
            },
            "observations": observations,
        }
