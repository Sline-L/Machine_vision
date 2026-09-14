"""Real GPU contention injector. Experiment harness only — not a Control action.

fault_mode is always real_resource_pressure. Do not confuse with inject_v5_latency.

v4 rejects compute-heavy GEMM/conv as V5 injectors (they raise DVFS
and often *lower* V5 latency). Calibration uses memory-bandwidth and
SM-occupancy contention. GPU util is not a proxy for V5_OVERLOAD.

v5 adds async multi-stream memory flood, host↔device unified-memory
pressure, and elementwise memory-bound kernels.
"""

from pathlib import Path
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time

INJECTOR_TYPE = "gpu_contention"
INJECTOR_VERSION = "5"
THIS_FILE = Path(__file__).resolve()
KINDS = ("bandwidth", "mem_async", "mem_host", "mem_elementwise", "mem_reserve", "sm", "mixed", "gemm", "conv")


def injector_config(
    kind="bandwidth",
    matrix=128,
    load_ms=100,
    idle_ms=0,
    bytes_mb=256,
    size=640,
    batch=1,
    channels=16,
    nice=None,
    streams=4,
    buffers=3,
    reserve_free_mb=512,
):
    return {
        "type": INJECTOR_TYPE,
        "version": INJECTOR_VERSION,
        "kind": str(kind),
        "matrix": int(matrix),
        "load_ms": float(load_ms),
        "idle_ms": float(idle_ms),
        "bytes_mb": int(bytes_mb),
        "reserve_free_mb": int(reserve_free_mb),
        "size": int(size),
        "batch": int(batch),
        "channels": int(channels),
        "streams": int(streams),
        "buffers": int(buffers),
        "nice": nice,
        "script": str(THIS_FILE),
    }


def injector_hash(config=None):
    config = injector_config() if config is None else dict(config)
    body = THIS_FILE.read_bytes() + json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def read_gpu_clock_mhz():
    """Best-effort sysfs GPU clock. None on hosts that do not expose it."""
    patterns = (
        "/sys/devices/gpu.*/devfreq/*/cur_freq",
        "/sys/class/devfreq/*gpu*/cur_freq",
        "/sys/class/devfreq/*/cur_freq",
        "/sys/kernel/debug/bpmp/debug/clk/gpcclk/rate",
        "/sys/kernel/debug/clk/gpcclk/clk_rate",
    )
    paths = []
    for pattern in patterns:
        paths.extend(sorted(glob.glob(pattern)))
    for path in paths:
        try:
            raw = Path(path).read_text(encoding="utf-8").strip().split()[0]
            value = float(raw)
        except (OSError, ValueError, IndexError):
            continue
        if value <= 0:
            continue
        if value > 10000:
            value = value / 1_000_000.0
        elif value > 20:
            value = value / 1000.0
        return round(value, 3)
    return None


def read_emc_mhz():
    """Best-effort EMC / memory-controller clock. None if sysfs is missing."""
    patterns = (
        "/sys/kernel/debug/bpmp/debug/clk/emc/rate",
        "/sys/kernel/debug/clk/emc/clk_rate",
        "/sys/class/devfreq/*emc*/cur_freq",
        "/sys/kernel/debug/bpmp/debug/clk/emc/floor",
    )
    paths = []
    for pattern in patterns:
        paths.extend(sorted(glob.glob(pattern)))
    for path in paths:
        try:
            raw = Path(path).read_text(encoding="utf-8").strip().split()[0]
            value = float(raw)
        except (OSError, ValueError, IndexError):
            continue
        if value <= 0:
            continue
        if value > 10000:
            value = value / 1_000_000.0
        elif value > 20:
            value = value / 1000.0
        return round(value, 3)
    return None


def read_power_mode():
    try:
        completed = subprocess.run(["nvpmodel", "-q"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return text or None


def read_tegrastats():
    """One-shot tegrastats sample. Returns GR3D % and power when available."""
    try:
        completed = subprocess.run(
            ["tegrastats", "--interval", "200", "--stop"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if not text:
        return {}
    line = text.splitlines()[-1]
    out = {}
    gr3d = re.search(r"GR3D_FREQ\s+(\d+)%", line)
    if gr3d:
        out["gr3d_pct"] = int(gr3d.group(1))
    vin = re.search(r"VDD_IN\s+(\d+)mW", line)
    if vin:
        out["vdd_in_mw"] = int(vin.group(1))
    return out


def _duty_loop(load_ms, idle_ms, work):
    load_s = max(0.0, float(load_ms) / 1000.0)
    idle_s = max(0.0, float(idle_ms) / 1000.0)
    while True:
        started = time.perf_counter()
        if load_s <= 0:
            work()
        else:
            while (time.perf_counter() - started) < load_s:
                work()
        if idle_s > 0:
            time.sleep(idle_s)


def _burn(kind, matrix, load_ms, idle_ms, bytes_mb, size, batch, channels, streams=4, buffers=3, reserve_free_mb=512):
    try:
        import torch
        import torch.nn as nn
    except ImportError as exc:
        raise SystemExit("gpu_contention 需要 torch") from exc
    if not torch.cuda.is_available():
        raise SystemExit("gpu_contention 需要 CUDA")
    device = torch.device("cuda:0")
    n_sm = max(32, min(int(matrix), 256))
    elems = max(1024, int(bytes_mb) * 1024 * 1024 // 4)
    nbuf = max(2, int(buffers))
    nstream = max(1, int(streams))

    def mem_once(bufs, index):
        dst = (index + 1) % len(bufs)
        bufs[index].add_(0.0001)
        bufs[dst].copy_(bufs[index])
        torch.cuda.synchronize()
        return dst

    def mem_async_once(stream_objs, bufs):
        for i, stream in enumerate(stream_objs):
            src = i % len(bufs)
            dst = (i + 1) % len(bufs)
            with torch.cuda.stream(stream):
                bufs[dst].copy_(bufs[src], non_blocking=True)
                bufs[src].mul_(1.0001)
        torch.cuda.synchronize()

    def sm_once(stream_objs, lefts, rights):
        for i, stream in enumerate(stream_objs):
            with torch.cuda.stream(stream):
                torch.mm(lefts[i], rights[i])
        torch.cuda.synchronize()

    if kind == "bandwidth":
        bufs = [torch.randn(elems, device=device) for _ in range(nbuf)]
        idx = {"i": 0}

        def work():
            idx["i"] = mem_once(bufs, idx["i"])

        _duty_loop(load_ms, idle_ms, work)
        return
    if kind == "mem_async":
        bufs = [torch.randn(elems, device=device) for _ in range(nbuf)]
        stream_objs = [torch.cuda.Stream() for _ in range(nstream)]
        _duty_loop(load_ms, idle_ms, lambda: mem_async_once(stream_objs, bufs))
        return
    if kind == "mem_host":
        pin = torch.randn(elems, pin_memory=True)
        gpu_bufs = [torch.randn(elems, device=device) for _ in range(max(2, nbuf))]
        stream_objs = [torch.cuda.Stream() for _ in range(nstream)]

        def host_once():
            for i, stream in enumerate(stream_objs):
                gb = gpu_bufs[i % len(gpu_bufs)]
                with torch.cuda.stream(stream):
                    gb.copy_(pin, non_blocking=True)
                    pin.copy_(gb, non_blocking=True)
            torch.cuda.synchronize()

        _duty_loop(load_ms, idle_ms, host_once)
        return
    if kind == "mem_elementwise":
        bufs = [torch.randn(elems, device=device) for _ in range(nbuf)]
        stream_objs = [torch.cuda.Stream() for _ in range(nstream)]

        def elem_once():
            for i, stream in enumerate(stream_objs):
                with torch.cuda.stream(stream):
                    bufs[i % len(bufs)].mul_(1.00001)
                    bufs[i % len(bufs)].add_(0.00001)
            torch.cuda.synchronize()

        _duty_loop(load_ms, idle_ms, elem_once)
        return
    if kind == "mem_reserve":
        blocks = []
        target_free = max(64, int(reserve_free_mb)) * 1024 * 1024

        def reserve_once():
            nonlocal blocks
            free_bytes, _total = torch.cuda.mem_get_info()
            if free_bytes <= target_free:
                return
            chunk = min(free_bytes - target_free, 256 * 1024 * 1024)
            elems_chunk = max(1024, chunk // 4)
            try:
                blocks.append(torch.empty(elems_chunk, device=device))
            except RuntimeError:
                pass

        def work():
            reserve_once()
            if blocks:
                blocks[-1].add_(0.0)

        _duty_loop(load_ms, idle_ms, work)
        return
    if kind == "sm":
        stream_objs = [torch.cuda.Stream() for _ in range(nstream)]
        lefts = [torch.randn(n_sm, n_sm, device=device) for _ in range(nstream)]
        rights = [torch.randn(n_sm, n_sm, device=device) for _ in range(nstream)]
        _duty_loop(load_ms, idle_ms, lambda: sm_once(stream_objs, lefts, rights))
        return
    if kind == "mixed":
        bufs = [torch.randn(max(1024, elems // 2), device=device) for _ in range(nbuf)]
        idx = {"i": 0}
        stream_objs = [torch.cuda.Stream() for _ in range(nstream)]
        lefts = [torch.randn(n_sm, n_sm, device=device) for _ in range(nstream)]
        rights = [torch.randn(n_sm, n_sm, device=device) for _ in range(nstream)]

        def work():
            sm_once(stream_objs, lefts, rights)
            idx["i"] = mem_once(bufs, idx["i"])

        _duty_loop(load_ms, idle_ms, work)
        return
    if kind == "gemm":
        left = torch.randn(max(64, int(matrix)), max(64, int(matrix)), device=device)
        right = torch.randn(max(64, int(matrix)), max(64, int(matrix)), device=device)

        def work():
            torch.mm(left, right)
            torch.cuda.synchronize()

        _duty_loop(load_ms, idle_ms, work)
        return
    ch = max(4, int(channels))
    net = nn.Sequential(
        nn.Conv2d(3, ch, 3, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(ch, ch, 3, padding=1),
    ).to(device)
    spatial = max(64, int(size))
    x = torch.randn(max(1, int(batch)), 3, spatial, spatial, device=device)

    def conv_once():
        net(x)
        torch.cuda.synchronize()

    _duty_loop(load_ms, idle_ms, conv_once)


class GpuContention:
    def __init__(
        self,
        python=None,
        kind="bandwidth",
        matrix=128,
        load_ms=100,
        idle_ms=0,
        bytes_mb=512,
        size=640,
        batch=1,
        channels=16,
        nice=None,
        sleep_ms=None,
        streams=4,
        buffers=3,
        reserve_free_mb=512,
    ):
        self.python = python or sys.executable
        self.kind = str(kind)
        self.matrix = int(matrix)
        if sleep_ms is not None and float(sleep_ms) > 0 and idle_ms == 0:
            idle_ms = float(sleep_ms)
        self.load_ms = float(load_ms)
        self.idle_ms = float(idle_ms)
        self.bytes_mb = int(bytes_mb)
        self.size = int(size)
        self.batch = int(batch)
        self.channels = int(channels)
        self.streams = int(streams)
        self.buffers = int(buffers)
        self.reserve_free_mb = int(reserve_free_mb)
        self.nice = nice
        self.proc = None
        self._err_handle = None

    def config(self):
        return injector_config(
            self.kind,
            self.matrix,
            self.load_ms,
            self.idle_ms,
            self.bytes_mb,
            self.size,
            self.batch,
            self.channels,
            self.nice,
            self.streams,
            self.buffers,
            self.reserve_free_mb,
        )

    def hash(self):
        return injector_hash(self.config())

    def start(self):
        self.stop()
        env = os.environ.copy()
        env.setdefault("CUDA_VISIBLE_DEVICES", "0")
        err_path = THIS_FILE.parent.parent / "results" / "gpu_contention.err"
        err_path.parent.mkdir(parents=True, exist_ok=True)
        handle = err_path.open("w", encoding="utf-8")
        cmd = [
            self.python,
            "-m",
            "edgemedic.gpu_pressure",
            "--burn",
            "--kind",
            self.kind,
            "--matrix",
            str(self.matrix),
            "--load-ms",
            str(self.load_ms),
            "--idle-ms",
            str(self.idle_ms),
            "--bytes-mb",
            str(self.bytes_mb),
            "--size",
            str(self.size),
            "--batch",
            str(self.batch),
            "--channels",
            str(self.channels),
            "--streams",
            str(self.streams),
            "--buffers",
            str(self.buffers),
            "--reserve-free-mb",
            str(self.reserve_free_mb),
        ]
        if self.nice is not None:
            cmd.extend(["--nice", str(int(self.nice))])
        self.proc = subprocess.Popen(
            cmd,
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
            handle = self._err_handle
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
                self._err_handle = None
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self.proc = None
        handle = self._err_handle
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
            self._err_handle = None


def main(argv=None):
    parser = argparse.ArgumentParser(description="GPU contention injector")
    parser.add_argument("--burn", action="store_true")
    parser.add_argument("--kind", choices=KINDS, default="bandwidth")
    parser.add_argument("--matrix", type=int, default=128)
    parser.add_argument("--load-ms", type=float, default=100.0)
    parser.add_argument("--idle-ms", type=float, default=0.0)
    parser.add_argument("--sleep-ms", type=float, default=None, help="legacy alias for --idle-ms")
    parser.add_argument("--bytes-mb", type=int, default=512)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--channels", type=int, default=16)
    parser.add_argument("--streams", type=int, default=4)
    parser.add_argument("--buffers", type=int, default=3)
    parser.add_argument("--reserve-free-mb", type=int, default=512)
    parser.add_argument("--nice", type=int, default=None)
    args = parser.parse_args(argv)
    idle = args.idle_ms if args.sleep_ms is None else args.sleep_ms
    if args.burn:
        if args.nice is not None:
            try:
                os.nice(int(args.nice))
            except OSError:
                pass
        _burn(
            args.kind,
            args.matrix,
            args.load_ms,
            idle,
            args.bytes_mb,
            args.size,
            args.batch,
            args.channels,
            args.streams,
            args.buffers,
            args.reserve_free_mb,
        )
        return 0
    cfg = injector_config(
        args.kind,
        args.matrix,
        args.load_ms,
        idle,
        args.bytes_mb,
        args.size,
        args.batch,
        args.channels,
        args.nice,
        args.streams,
        args.buffers,
        args.reserve_free_mb,
    )
    print(
        json.dumps(
            {
                "type": INJECTOR_TYPE,
                "version": INJECTOR_VERSION,
                "hash": injector_hash(cfg),
                "config": cfg,
                "gpu_clock_mhz": read_gpu_clock_mhz(),
                "emc_mhz": read_emc_mhz(),
                "power_mode": read_power_mode(),
                "tegrastats": read_tegrastats(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
