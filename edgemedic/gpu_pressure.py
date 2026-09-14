"""Real GPU contention injector for A3. Not a SystemSnapshot patch.

This is an experiment harness, not an EdgeMedic Control action. It must stay
on until recovery/timeout. fault_mode is always real_resource_pressure.
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
INJECTOR_VERSION = "1"
THIS_FILE = Path(__file__).resolve()


def injector_config(matrix=1024, sleep_ms=0):
    return {
        "type": INJECTOR_TYPE,
        "version": INJECTOR_VERSION,
        "matrix": int(matrix),
        "sleep_ms": float(sleep_ms),
        "script": str(THIS_FILE),
    }


def injector_hash(config=None):
    config = injector_config() if config is None else dict(config)
    body = THIS_FILE.read_bytes() + json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _burn(matrix, sleep_ms):
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("gpu_contention 需要 torch") from exc
    if not torch.cuda.is_available():
        raise SystemExit("gpu_contention 需要 CUDA")
    device = torch.device("cuda:0")
    n = max(64, int(matrix))
    left = torch.randn(n, n, device=device)
    right = torch.randn(n, n, device=device)
    pause = max(0.0, float(sleep_ms) / 1000.0)
    while True:
        torch.mm(left, right)
        torch.cuda.synchronize()
        if pause:
            time.sleep(pause)


class GpuContention:
    def __init__(self, python=None, matrix=1024, sleep_ms=0):
        self.python = python or sys.executable
        self.matrix = int(matrix)
        self.sleep_ms = float(sleep_ms)
        self.proc = None

    def config(self):
        return injector_config(self.matrix, self.sleep_ms)

    def hash(self):
        return injector_hash(self.config())

    def start(self):
        self.stop()
        env = os.environ.copy()
        env.setdefault("CUDA_VISIBLE_DEVICES", "0")
        self.proc = subprocess.Popen(
            [
                self.python,
                "-m",
                "edgemedic.gpu_pressure",
                "--burn",
                "--matrix",
                str(self.matrix),
                "--sleep-ms",
                str(self.sleep_ms),
            ],
            cwd=str(THIS_FILE.parent.parent),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        if self.proc.poll() is not None:
            raise RuntimeError("gpu_contention 进程立即退出（需要板上 CUDA torch）")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="A3 GPU contention injector")
    parser.add_argument("--burn", action="store_true")
    parser.add_argument("--matrix", type=int, default=1024)
    parser.add_argument("--sleep-ms", type=float, default=0.0)
    args = parser.parse_args(argv)
    if args.burn:
        _burn(args.matrix, args.sleep_ms)
        return 0
    print(json.dumps({"type": INJECTOR_TYPE, "version": INJECTOR_VERSION, "hash": injector_hash(injector_config(args.matrix, args.sleep_ms))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
