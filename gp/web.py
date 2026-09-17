"""FastAPI surface for GearPro's browser interface."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets

from .auth import SessionManager
from .config import PROJECT_ROOT, RUNTIME_ROOT
from .runtime import GearProRuntime


API_PREFIX = "/api/v2"
LEGACY_API_PREFIX = "/api/v1"
STATIC_ROOT = PROJECT_ROOT / "gp" / "static"
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def _agent_base():
    return os.getenv("EDGEMEDIC_STATUS_URL", "http://127.0.0.1:8790").rstrip("/")


def _fetch_agent_status():
    import json
    from urllib.error import URLError
    from urllib.request import urlopen

    try:
        with urlopen(_agent_base() + "/status", timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "service": "edgemedic-agent",
            "available": False,
            "error": str(exc),
            "monitoring": False,
            "llm_ready": False,
            "note": "Agent service unreachable",
        }


def _notify_agent(path, payload=None):
    import json
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    raw = json.dumps(payload or {}).encode("utf-8")
    request = Request(
        _agent_base() + "/" + path.lstrip("/"),
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _agent_command(path, payload=None):
    """POST to Agent; raise if unreachable so GUI can show the failure."""
    import json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    from fastapi import HTTPException

    raw = json.dumps(payload or {}).encode("utf-8")
    request = Request(
        _agent_base() + "/" + path.lstrip("/"),
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=2.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"error": body or str(exc)}
        raise HTTPException(status_code=exc.code, detail=detail.get("error") or detail) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"Agent service unreachable: {exc}") from exc


def _raise_control(result):
    from fastapi import HTTPException

    if not result.get("accepted"):
        raise HTTPException(status_code=400, detail=result.get("error") or "动作被拒绝")
    if result.get("error") and not result.get("executed"):
        raise HTTPException(status_code=500, detail=result["error"])


def create_app(config, runtime=None, sessions=None, manage_lifespan=True):
    try:
        from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
        from fastapi.responses import JSONResponse, StreamingResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError("Web 依赖未安装，请运行 python -m pip install -r requirements.txt") from exc

    runtime = runtime or GearProRuntime(config)
    sessions = sessions or SessionManager(os.getenv("GEARPRO_WEB_PASSWORD", ""))

    @asynccontextmanager
    async def lifespan(_app):
        if manage_lifespan:
            runtime.startup()
        yield
        if manage_lifespan:
            runtime.shutdown()

    app = FastAPI(
        title="GearPro Web",
        version="2.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.runtime = runtime
    app.state.sessions = sessions

    def session_token(request: Request):
        token = request.cookies.get(SessionManager.COOKIE_NAME)
        if not sessions.validate(token):
            raise HTTPException(status_code=401, detail="请先登录")
        return token

    def controller(request: Request):
        token = session_token(request)
        if not sessions.owns_control(token):
            raise HTTPException(status_code=423, detail="请先取得操作权限")
        sessions.heartbeat(token)
        return token

    def api_version(target):
        return "api.v1" if target.url.path.startswith(LEGACY_API_PREFIX) else "api.v2"

    def runtime_state(target, token):
        return runtime.state(sessions.control_state(token), api_version=api_version(target))

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def permission_error_handler(_request, exc):
        return JSONResponse(status_code=423, content={"detail": str(exc)})

    @app.get(f"{API_PREFIX}/session")
    @app.get(f"{LEGACY_API_PREFIX}/session")
    async def session_info(request: Request):
        token = request.cookies.get(SessionManager.COOKIE_NAME)
        return {"authenticated": sessions.validate(token), "password_required": sessions.password_required}

    @app.post(f"{API_PREFIX}/session/login")
    @app.post(f"{LEGACY_API_PREFIX}/session/login")
    async def login(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            token = sessions.login(body.get("password", ""), body.get("label", "操作终端"))
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            SessionManager.COOKIE_NAME,
            token,
            httponly=True,
            samesite="strict",
            max_age=int(sessions.session_ttl),
        )
        return response

    @app.post(f"{API_PREFIX}/session/logout")
    @app.post(f"{LEGACY_API_PREFIX}/session/logout")
    async def logout(request: Request):
        token = request.cookies.get(SessionManager.COOKIE_NAME)
        if token:
            sessions.logout(token)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(SessionManager.COOKIE_NAME)
        return response

    @app.get(f"{API_PREFIX}/state")
    @app.get(f"{LEGACY_API_PREFIX}/state")
    async def state(request: Request):
        token = session_token(request)
        return runtime_state(request, token)

    @app.post(f"{API_PREFIX}/control/acquire")
    @app.post(f"{LEGACY_API_PREFIX}/control/acquire")
    async def acquire(request: Request):
        return sessions.acquire(session_token(request))

    @app.post(f"{API_PREFIX}/control/release")
    @app.post(f"{LEGACY_API_PREFIX}/control/release")
    async def release(request: Request):
        token = session_token(request)
        sessions.release(token)
        return sessions.control_state(token)

    @app.post(f"{API_PREFIX}/inspection/start")
    @app.post(f"{LEGACY_API_PREFIX}/inspection/start")
    async def start_inspection(request: Request):
        token = controller(request)
        result = await asyncio.to_thread(runtime.human_action, "resume_inspection", {})
        _raise_control(result)
        await asyncio.to_thread(_notify_agent, "monitor/start", {"arm_recovery": False})
        return runtime_state(request, token)

    @app.post(f"{API_PREFIX}/inspection/stop")
    @app.post(f"{LEGACY_API_PREFIX}/inspection/stop")
    async def stop_inspection(request: Request):
        token = controller(request)
        result = await asyncio.to_thread(runtime.human_action, "pause_inspection", {})
        _raise_control(result)
        await asyncio.to_thread(_notify_agent, "monitor/stop", {})
        return runtime_state(request, token)

    @app.get(f"{API_PREFIX}/agent/status")
    @app.get(f"{LEGACY_API_PREFIX}/agent/status")
    async def agent_status(request: Request):
        session_token(request)
        return await asyncio.to_thread(_fetch_agent_status)

    @app.post(f"{API_PREFIX}/agent/recovery/arm")
    @app.post(f"{LEGACY_API_PREFIX}/agent/recovery/arm")
    async def agent_recovery_arm(request: Request):
        """Arm low-risk recovery posts. Requires controller. Does not change observe_only agents."""
        controller(request)
        result = await asyncio.to_thread(_agent_command, "recovery/arm", {})
        return result

    @app.post(f"{API_PREFIX}/agent/recovery/disarm")
    @app.post(f"{LEGACY_API_PREFIX}/agent/recovery/disarm")
    async def agent_recovery_disarm(request: Request):
        controller(request)
        result = await asyncio.to_thread(_agent_command, "recovery/disarm", {})
        return result

    @app.post(f"{API_PREFIX}/source/camera")
    @app.post(f"{LEGACY_API_PREFIX}/source/camera")
    async def use_camera(request: Request):
        token = controller(request)
        result = await asyncio.to_thread(runtime.human_action, "use_camera", {})
        _raise_control(result)
        return runtime_state(request, token)

    @app.post(f"{API_PREFIX}/source/video")
    @app.post(f"{LEGACY_API_PREFIX}/source/video")
    async def upload_video(request: Request, file: UploadFile = File(...)):
        token = controller(request)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in VIDEO_SUFFIXES:
            raise HTTPException(status_code=400, detail="不支持的视频格式")
        maximum = int(os.getenv("GEARPRO_MAX_UPLOAD_MB", "2048")) * 1024 * 1024
        uploads = RUNTIME_ROOT / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        destination = uploads / f"{secrets.token_hex(16)}{suffix}"
        size = 0
        try:
            with destination.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise HTTPException(status_code=413, detail="视频文件超过上传限制")
                    output.write(chunk)
            result = await asyncio.to_thread(
                runtime.human_action,
                "use_video",
                {"path": str(destination), "managed": True},
            )
            _raise_control(result)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return runtime_state(request, token)

    @app.put(f"{API_PREFIX}/settings")
    @app.put(f"{LEGACY_API_PREFIX}/settings")
    async def update_settings(request: Request):
        token = controller(request)
        values = await request.json()
        if not isinstance(values, dict):
            raise HTTPException(status_code=400, detail="设置必须是 JSON 对象")
        result = await asyncio.to_thread(runtime.human_action, "apply_settings", values)
        _raise_control(result)
        return runtime_state(request, token)

    @app.post(f"{API_PREFIX}/stats/reset")
    @app.post(f"{LEGACY_API_PREFIX}/stats/reset")
    async def reset_stats(request: Request):
        token = controller(request)
        result = await asyncio.to_thread(runtime.human_action, "reset_stats", {})
        _raise_control(result)
        return runtime_state(request, token)

    @app.get(f"{API_PREFIX}/stream")
    @app.get(f"{LEGACY_API_PREFIX}/stream")
    async def stream(request: Request, view: str = "auto"):
        session_token(request)
        if view not in ("auto", "raw", "annotated"):
            raise HTTPException(status_code=400, detail="无效的画面类型")

        async def frames():
            delay = 1.0 / max(1.0, float(config.stream_fps))
            while True:
                if await request.is_disconnected():
                    return
                jpeg = await asyncio.to_thread(runtime.jpeg, view)
                if jpeg is not None:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(delay)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket(f"{API_PREFIX}/events")
    @app.websocket(f"{LEGACY_API_PREFIX}/events")
    async def events(websocket: WebSocket):
        token = websocket.cookies.get(SessionManager.COOKIE_NAME)
        if not sessions.validate(token):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            while sessions.validate(token):
                await websocket.send_json(
                    runtime.state(sessions.control_state(token), api_version=api_version(websocket))
                )
                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                    if message.get("type") == "control_heartbeat":
                        sessions.heartbeat(token)
                except asyncio.TimeoutError:
                    pass
        except Exception:
            return

    if STATIC_ROOT.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="web")
    return app
