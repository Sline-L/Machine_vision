"""Optional research-only capture freeze. Off unless GEARPRO_RESEARCH_INJECT is set.

research injector only
requires GEARPRO_RESEARCH_INJECT=1
does not mutate health state
not enabled by default
"""

from pathlib import Path
import os

_DEFAULT_FREEZE = "/tmp/gearpro-freeze-camera"


def research_inject_enabled():
    return os.getenv("GEARPRO_RESEARCH_INJECT", "").strip().lower() in {"1", "true", "yes", "on"}


def freeze_camera_requested():
    if not research_inject_enabled():
        return False
    return Path(os.getenv("GEARPRO_INJECT_FREEZE_CAMERA", _DEFAULT_FREEZE)).is_file()


def clear_research_camera_freeze():
    if not research_inject_enabled():
        return
    path = Path(os.getenv("GEARPRO_INJECT_FREEZE_CAMERA", _DEFAULT_FREEZE))
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def allow_restart_camera(source):
    """Live camera was already allowed. Replay is needed for freeze recovery.

    File-video mode stays blocked. This does not widen production camera authority.
    """
    return source != "video"
