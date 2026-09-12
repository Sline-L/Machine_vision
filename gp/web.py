"""FastAPI surface for GearPro's browser interface."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets

from .auth import SessionManager
from .config import PROJECT_ROOT, RUNTIME_ROOT
from .runtime import GearProRuntime


API_PREFIX = "/api/v1"
STATIC_ROOT = PROJECT_ROOT / "gp" / "static"
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


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
        version="1.0.0",
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

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def permission_error_handler(_request, exc):
        return JSONResponse(status_code=423, content={"detail": str(exc)})

    @app.get(f"{API_PREFIX}/session")
    async def session_info(request: Request):
        token = request.cookies.get(SessionManager.COOKIE_NAME)
        return {"authenticated": sessions.validate(token), "password_required": sessions.password_required}

    @app.post(f"{API_PREFIX}/session/login")
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
    async def logout(request: Request):
        token = request.cookies.get(SessionManager.COOKIE_NAME)
        if token:
            sessions.logout(token)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(SessionManager.COOKIE_NAME)
        return response

    @app.get(f"{API_PREFIX}/state")
    async def state(request: Request):
        token = session_token(request)
        return runtime.state(sessions.control_state(token))

    @app.post(f"{API_PREFIX}/control/acquire")
    async def acquire(request: Request):
        return sessions.acquire(session_token(request))

    @app.post(f"{API_PREFIX}/control/release")
    async def release(request: Request):
        token = session_token(request)
        sessions.release(token)
        return sessions.control_state(token)

    @app.post(f"{API_PREFIX}/inspection/start")
    async def start_inspection(request: Request):
        token = controller(request)
        runtime.start_inspection()
        return runtime.state(sessions.control_state(token))

    @app.post(f"{API_PREFIX}/inspection/stop")
    async def stop_inspection(request: Request):
        token = controller(request)
        runtime.stop_inspection()
        return runtime.state(sessions.control_state(token))

    @app.post(f"{API_PREFIX}/source/camera")
    async def use_camera(request: Request):
        token = controller(request)
        await asyncio.to_thread(runtime.use_camera)
        return runtime.state(sessions.control_state(token))

    @app.post(f"{API_PREFIX}/source/video")
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
            await asyncio.to_thread(runtime.use_video, destination, True)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return runtime.state(sessions.control_state(token))

    @app.put(f"{API_PREFIX}/settings")
    async def update_settings(request: Request):
        token = controller(request)
        values = await request.json()
        if not isinstance(values, dict):
            raise HTTPException(status_code=400, detail="设置必须是 JSON 对象")
        await asyncio.to_thread(runtime.update_settings, values)
        return runtime.state(sessions.control_state(token))

    @app.post(f"{API_PREFIX}/stats/reset")
    async def reset_stats(request: Request):
        token = controller(request)
        runtime.reset_stats()
        return runtime.state(sessions.control_state(token))

    @app.get(f"{API_PREFIX}/stream")
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
    async def events(websocket: WebSocket):
        token = websocket.cookies.get(SessionManager.COOKIE_NAME)
        if not sessions.validate(token):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            while sessions.validate(token):
                await websocket.send_json(runtime.state(sessions.control_state(token)))
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
