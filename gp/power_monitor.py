"""Background power / utilisation sampling for benchmarks.

Jetson: `tegrastats` reports module input power (VDD_IN, INA3221 rails), GPU
load (GR3D_FREQ), memory-controller load (EMC_FREQ), DLA state, shared RAM and
temperatures. Desktop/laptop NVIDIA GPU: `nvidia-smi` reports board power of
the discrete GPU only, which is not comparable with Jetson VDD_IN.
"""

import re
import shutil
import subprocess
import threading
import time

RAIL = re.compile(r"\b((?:VDD|VIN|POM)_[A-Z0-9_]+) (\d+)(?:mW)?/(\d+)(?:mW)?")
TEMPERATURE = re.compile(r"\b([A-Za-z0-9_]+)@(-?[\d.]+)C\b")
RAM = re.compile(r"\bRAM (\d+)/(\d+)MB")
GR3D = re.compile(r"\bGR3D_FREQ (\d+)%")
EMC = re.compile(r"\bEMC_FREQ (\d+)%")
DLA = re.compile(r"\b(NVDLA\d) (off|\S+)")
CPU = re.compile(r"\bCPU \[([^\]]*)\]")


def parse_tegrastats_line(line):
    """Parse one tegrastats line into a flat dict of measured fields only."""
    sample = {}
    match = RAM.search(line)
    if match:
        sample["ram_used_mb"] = float(match.group(1))
        sample["ram_total_mb"] = float(match.group(2))
    match = GR3D.search(line)
    if match:
        sample["gpu_util_pct"] = float(match.group(1))
    match = EMC.search(line)
    if match:
        sample["emc_util_pct"] = float(match.group(1))
    match = CPU.search(line)
    if match:
        loads = [float(core.split("%")[0]) for core in match.group(1).split(",") if "%" in core]
        if loads:
            sample["cpu_util_pct"] = sum(loads) / len(loads)
    for name, state in DLA.findall(line):
        # tegrastats only exposes DLA on/off and clock, not a utilisation percentage.
        sample[f"{name.lower()}_active"] = 0.0 if state == "off" else 1.0
    for name, value in TEMPERATURE.findall(line):
        sample[f"temp_{name.lower()}_c"] = float(value)
    for name, current, _average in RAIL.findall(line):
        sample[f"{name.lower()}_w"] = float(current) / 1000.0
    if "vdd_in_w" in sample:
        sample["power_w"] = sample["vdd_in_w"]
    return sample


NVIDIA_SMI_FIELDS = ("power.draw", "utilization.gpu", "memory.used", "temperature.gpu", "clocks.sm")
NVIDIA_SMI_KEYS = ("power_w", "gpu_util_pct", "gpu_mem_mb", "temp_gpu_c", "sm_clock_mhz")


def parse_nvidia_smi_line(line):
    sample = {}
    for key, value in zip(NVIDIA_SMI_KEYS, line.split(",")):
        value = value.strip()
        try:
            sample[key] = float(value)
        except ValueError:
            continue  # "[N/A]" or "[Not Supported]"
    return sample


class CommandSampler:
    """Run a line-oriented sampling command and timestamp each parsed line."""

    def __init__(self, source, command, parser):
        self.source = source
        self.command = command
        self.parser = parser
        self.samples = []
        self._process = None
        self._thread = None

    def start(self):
        self._process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read, name=f"{self.source}-sampler", daemon=True)
        self._thread.start()
        return self

    def _read(self):
        for line in self._process.stdout:
            sample = self.parser(line)
            if sample:
                sample["t"] = time.monotonic()
                self.samples.append(sample)

    def stop(self):
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
        if self._thread is not None:
            self._thread.join(timeout=3)
        return self.samples


def create_sampler(kind="auto", interval_ms=100, cuda=True):
    """Return a sampler or None. `auto` prefers tegrastats, then nvidia-smi."""
    if kind == "auto":
        if shutil.which("tegrastats"):
            kind = "tegrastats"
        elif cuda and shutil.which("nvidia-smi"):
            kind = "nvidia-smi"
        else:
            return None
    if kind == "none":
        return None
    if kind == "tegrastats":
        return CommandSampler(kind, ["tegrastats", "--interval", str(int(interval_ms))], parse_tegrastats_line)
    if kind == "nvidia-smi":
        command = [
            "nvidia-smi",
            "--query-gpu=" + ",".join(NVIDIA_SMI_FIELDS),
            "--format=csv,noheader,nounits",
            "-i",
            "0",
            "-lms",
            str(int(interval_ms)),
        ]
        return CommandSampler(kind, command, parse_nvidia_smi_line)
    raise ValueError(f"未知功耗采样方式：{kind}")


def window(samples, start, end):
    return [sample for sample in samples if start <= sample["t"] <= end]


def energy_joules(samples, key="power_w"):
    """Trapezoidal integral of power over the sampled timestamps."""
    points = [(sample["t"], sample[key]) for sample in samples if key in sample]
    return sum((t1 - t0) * (p0 + p1) / 2.0 for (t0, p0), (t1, p1) in zip(points, points[1:]))
