"""Real GPU contention injector for A3. Not a SystemSnapshot patch.

This is an experiment harness, not an EdgeMedic Control action. It must stay
on until recovery/timeout. fault_mode is always real_resource_pressure.

GEMM alone did not push Scratch V5 p95 over 200 ms on NX. The default
workload is a persistent Conv2d (imgsz-like) that shares the GPU with V5.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

INJECTOR_TYPE = "gpu_contention"
INJECTOR_VERSION = "2"
THIS_FILE = Path(__file__).resolve()


def injector_config(kind="conv", matrix=1024, sleep_ms=0, size=640, batch=1, channels=16):
    return {
        "type": INJECTOR_TYPE,
        "version": INJECTOR_VERSION,
        "kind": str(kind),
        "matrix": int(matrix),
        "sleep_ms": float(sleep_ms),
        "size": int(size),
        "batch": int(batch),
        "channels": int(channels),
        "script": str(THIS_FILE),
    }


def injector_hash(config=None):
    config = injector_config() if config is None else dict(config)
    body = THIS_FILE.read_bytes() + json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _burn(kind, matrix, sleep_ms, size, batch, channels):
    try:
        import torch
        import torch.nn as nn
    except ImportError as exc:
        raise SystemExit("gpu_contention 需要 torch") from exc
    if not torch.cuda.is_available():
        raise SystemExit("gpu_contention 需要 CUDA")
    device = torch.device("cuda:0")
    pause = max(0.0, float(sleep_ms) / 1000.0)
    if kind == "gemm":
        n = max(64, int(matrix))
        left = torch.randn(n, n, device=device)
        right = torch.randn(n, n, device=device)
        while True:
            torch.mm(left, right)
            torch.cuda.synchronize()
            if pause:
                time.sleep(pause)
        return
    ch = max(4, int(channels))
    net = nn.Sequential(
        nn.Conv2d(3, ch, 3, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(ch, ch, 3, padding=1),
    ).to(device)
    spatial = max(64, int(size))
    x = torch.randn(max(1, int(batch)), 3, spatial, spatial, device=device)
    while True:
        net(x)
        torch.cuda.synchronize()
        if pause:
            time.sleep(pause)


class GpuContention:
    def __init__(self, python=None, kind="conv", matrix=1024, sleep_ms=0, size=640, batch=1, channels=16):
        self.python = python or sys.executable
        self.kind = str(kind)
        self.matrix = int(matrix)
        self.sleep_ms = float(sleep_ms)
        self.size = int(size)
        self.batch = int(batch)
        self.channels = int(channels)
        self.proc = None

    def config(self):
        return injector_config(self.kind, self.matrix, self.sleep_ms, self.size, self.batch, self.channels)

    def hash(self):
        return injector_hash(self.config())

    def start(self):
        self.stop()
        env = os.environ.copy()
        env.setdefault("CUDA_VISIBLE_DEVICES", "0")
        err_path = THIS_FILE.parent.parent / "results" / "gpu_contention.err"
        err_path.parent.mkdir(parents=True, exist_ok=True)
        handle = err_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [
                self.python,
                "-m",
                "edgemedic.gpu_pressure",
                "--burn",
                "--kind",
                self.kind,
                "--matrix",
                str(self.matrix),
                "--sleep-ms",
                str(self.sleep_ms),
                "--size",
                str(self.size),
                "--batch",
                str(self.batch),
                "--channels",
                str(self.channels),
            ],
            cwd=str(THIS_FILE.parent.parent),
            env=env,
            stdout=handle,
            stderr=handle,
        )
        self._err_handle = handle
        time.sleep(1.0)
        if self.proc.poll() is not None:
            handle.close()
            detail = err_path.read_text(encoding="utf-8", errors="replace")[-500:]
            raise RuntimeError(f"gpu_contention 进程立即退出：{detail}")
        return {"pid": self.proc.pid, "config": self.config(), "hash": self.hash()}

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self.proc = None
        handle = getattr(self, "_err_handle", None)
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
            self._err_handle = None


def main(argv=None):
    parser = argparse.ArgumentParser(description="A3 GPU contention injector")
    parser.add_argument("--burn", action="store_true")
    parser.add_argument("--kind", choices=("conv", "gemm"), default="conv")
    parser.add_argument("--matrix", type=int, default=1024)
    parser.add_argument("--sleep-ms", type=float, default=0.0)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--channels", type=int, default=16)
    args = parser.parse_args(argv)
    if args.burn:
        _burn(args.kind, args.matrix, args.sleep_ms, args.size, args.batch, args.channels)
        return 0
    cfg = injector_config(args.kind, args.matrix, args.sleep_ms, args.size, args.batch, args.channels)
    print(json.dumps({"type": INJECTOR_TYPE, "version": INJECTOR_VERSION, "hash": injector_hash(cfg), "config": cfg}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
