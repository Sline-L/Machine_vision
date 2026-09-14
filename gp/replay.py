"""Disk image replay as a CameraCapture-compatible frame producer."""

from collections import deque
from pathlib import Path
import hashlib
import json
import shutil
import threading
import time

import cv2


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
LOCKED_MARKERS = ("test_scratch",)
MANIFEST_NAME = "replay_manifest.json"


class ReplayPackError(ValueError):
    pass


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replay_pack_hash(manifest):
    body = {
        "replay_pack_id": manifest.get("replay_pack_id"),
        "source_repo": manifest.get("source_repo"),
        "source_commit": manifest.get("source_commit"),
        "locked_test": manifest.get("locked_test"),
        "files": manifest.get("files") or [],
    }
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def frames_dir_for(directory):
    directory = Path(directory)
    nested = directory / "frames"
    if nested.is_dir():
        return nested
    return directory


def load_replay_pack(directory):
    directory = Path(directory)
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ReplayPackError(f"缺少 {MANIFEST_NAME}：{directory}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReplayPackError("replay manifest 必须是对象")
    if manifest.get("locked_test") is not False:
        raise ReplayPackError("replay pack 必须 locked_test=false，不能使用锁定测试集")
    for marker in LOCKED_MARKERS:
        blob = json.dumps(manifest)
        if marker in blob:
            raise ReplayPackError(f"replay pack 引用了锁定集 {marker}")
    frames = frames_dir_for(directory)
    files = manifest.get("files") or []
    if not files:
        raise ReplayPackError("replay pack files 为空")
    paths = []
    for item in files:
        name = item.get("name")
        path = frames / name
        if not path.is_file():
            raise ReplayPackError(f"缺少 replay 帧：{name}")
        actual = _sha256_file(path)
        listed = str(item.get("sha256") or "").lower()
        if listed and listed != actual:
            raise ReplayPackError(f"{name} SHA256 与 manifest 不一致")
        paths.append(path)
    pack_hash = replay_pack_hash(manifest)
    return {
        "directory": directory,
        "frames_dir": frames,
        "paths": paths,
        "manifest": manifest,
        "replay_pack_id": manifest.get("replay_pack_id"),
        "replay_pack_hash": pack_hash,
    }


def build_replay_pack(source_dir, dest_dir, replay_pack_id, source_repo, source_commit, limit=40):
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)
    if any(marker in str(source_dir).replace("\\", "/") for marker in LOCKED_MARKERS):
        raise ReplayPackError("拒绝从锁定测试目录构建 replay pack")
    images = sorted(
        path for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        and "test_scratch" not in str(path).replace("\\", "/")
    )[: max(1, int(limit))]
    if not images:
        raise ReplayPackError(f"源目录没有可用图片：{source_dir}")
    frames = dest_dir / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)
    files = []
    for index, src in enumerate(images, start=1):
        name = f"{index:06d}{src.suffix.lower()}"
        dest = frames / name
        shutil.copy2(src, dest)
        rel = str(src).replace("\\", "/")
        try:
            rel = str(src.relative_to(source_dir)).replace("\\", "/")
        except ValueError:
            pass
        files.append(
            {
                "name": name,
                "sha256": _sha256_file(dest),
                "source_path": rel,
            }
        )
    manifest = {
        "replay_pack_id": replay_pack_id,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "locked_test": False,
        "sample_count": len(files),
        "source_root": str(source_dir),
        "files": files,
    }
    manifest["replay_pack_hash"] = replay_pack_hash(manifest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return load_replay_pack(dest_dir)


def list_replay_images(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"找不到 replay 目录：{directory}")
    if (directory / MANIFEST_NAME).is_file():
        return load_replay_pack(directory)["paths"]
    images = sorted(
        path for path in frames_dir_for(directory).iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise FileNotFoundError(f"replay 目录没有图片：{directory}")
    return images


class ReplayCapture:
    """Publish dataset images into LatestFrame at camera_fps. Not a live sensor."""

    def __init__(self, config, frame_store, on_complete=None):
        self.config = config
        self.frame_store = frame_store
        self.on_complete = on_complete
        self.error_message = ""
        self.read_failures = 0
        self._ok_stamps = deque()
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._opened = False
        self._images = []

    @property
    def device_path(self):
        directory = getattr(self.config, "replay_dir", None)
        return f"replay:{directory}" if directory is not None else "replay"

    @property
    def opened(self):
        with self._lock:
            return self._opened

    @property
    def actual_fps(self):
        now = time.monotonic()
        with self._stats_lock:
            while self._ok_stamps and now - self._ok_stamps[0] > 1.0:
                self._ok_stamps.popleft()
            return float(len(self._ok_stamps))

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return True
        try:
            self._images = list_replay_images(self.config.replay_dir)
        except FileNotFoundError as exc:
            self.error_message = str(exc)
            with self._lock:
                self._opened = False
            return False
        self._stop_event.clear()
        with self._lock:
            self._opened = True
        self.error_message = ""
        self.read_failures = 0
        with self._stats_lock:
            self._ok_stamps.clear()
        self._thread = threading.Thread(target=self._loop, name="gearpro-replay", daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        frame_period = 1.0 / max(1, int(self.config.camera_fps))
        index = 0
        loop = bool(getattr(self.config, "replay_loop", True))
        while not self._stop_event.is_set():
            started = time.monotonic()
            path = self._images[index]
            frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if frame is None:
                self.read_failures += 1
                self.error_message = f"无法读取 replay 图片：{path.name}"
            else:
                self.read_failures = 0
                with self._stats_lock:
                    self._ok_stamps.append(time.monotonic())
                self.frame_store.publish(frame)
            index += 1
            if index >= len(self._images):
                if not loop:
                    callback = self.on_complete
                    self._stop_event.set()
                    with self._lock:
                        self._opened = True
                    if callback is not None:
                        callback()
                    return
                index = 0
            remaining = frame_period - (time.monotonic() - started)
            if remaining > 0:
                self._stop_event.wait(remaining)

    def stop(self):
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        with self._lock:
            self._opened = False
        self._thread = None

    def restart(self):
        self.stop()
        return self.start()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Build or verify a GearPro replay pack")
    parser.add_argument("--source", type=Path, help="non-locked image directory from Machine_vision_dataset")
    parser.add_argument("--dest", type=Path, default=Path("tests/replay"))
    parser.add_argument("--pack-id", default="gearpro-replay-v1")
    parser.add_argument("--source-repo", default="Sline-L/Machine_vision_dataset")
    parser.add_argument("--source-commit", required=False, default="")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--verify", type=Path, default=None, help="verify an existing pack")
    args = parser.parse_args(argv)
    if args.verify:
        pack = load_replay_pack(args.verify)
        print(json.dumps({"replay_pack_id": pack["replay_pack_id"], "replay_pack_hash": pack["replay_pack_hash"], "n": len(pack["paths"])}, indent=2))
        return 0
    if args.source is None:
        raise SystemExit("需要 --source 或 --verify")
    pack = build_replay_pack(
        args.source,
        args.dest,
        args.pack_id,
        args.source_repo,
        args.source_commit,
        limit=args.limit,
    )
    print(json.dumps({"replay_pack_id": pack["replay_pack_id"], "replay_pack_hash": pack["replay_pack_hash"], "n": len(pack["paths"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
