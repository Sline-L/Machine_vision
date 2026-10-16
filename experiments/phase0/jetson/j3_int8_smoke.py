#!/usr/bin/env python3
"""J3: INT8 EntropyCalibrator2 smoke test (C2, 8 calib tensors)."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pycuda.autoinit  # noqa: F401
import pycuda.driver as cuda
import tensorrt as trt

PHASE0 = Path(__file__).resolve().parent
if PHASE0.name == "jetson":
    PHASE0 = PHASE0.parent

TENSOR_DIR = PHASE0 / "data/tensors"
ONNX = PHASE0 / "engines/onnx/p_resnet18_384_w1.onnx"
CACHE_DIR = PHASE0 / "data/calib_cache"
ENGINE_DIR = PHASE0 / "engines/trt"
WORKSPACE_GB = 4


class EntropyCalibrator(trt.IInt8EntropyCalibrator2):
    def __init__(self, paths: list[Path], cache_path: Path):
        super().__init__()
        self.paths = paths
        self.i = 0
        self.cache_path = str(cache_path)
        sample = np.load(paths[0]).astype(np.float32).ravel()
        self.nbytes = sample.nbytes
        self.d_input = cuda.mem_alloc(self.nbytes)

    def get_batch_size(self):
        return 1

    def get_batch(self, names):
        if self.i >= len(self.paths):
            return None
        arr = np.load(self.paths[self.i]).astype(np.float32).ravel()
        if arr.nbytes != self.nbytes:
            raise RuntimeError("calib tensor size mismatch")
        cuda.memcpy_htod(self.d_input, arr)
        self.i += 1
        return [int(self.d_input)]

    def read_calibration_cache(self):
        if Path(self.cache_path).is_file():
            return Path(self.cache_path).read_bytes()
        return None

    def write_calibration_cache(self, cache):
        Path(self.cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.cache_path).write_bytes(cache)


def pick_calib_stems(n: int = 8) -> list[str]:
    manifest = PHASE0 / "results/pc/calib_manifest.csv"
    stems = []
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            stems.append(row["stem"])
    return stems[:n]


def main() -> int:
    logger = trt.Logger(trt.Logger.INFO)
    stems = pick_calib_stems(8)
    paths = [TENSOR_DIR / f"{s}_cls384.npy" for s in stems]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "j3_c2_entropy_smoke.cache"
    calibrator = EntropyCalibrator(paths, cache_path)

    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, logger)
    if not parser.parse(ONNX.read_bytes()):
        for i in range(parser.num_errors):
            print(parser.get_error(i), file=sys.stderr)
        return 1

    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, WORKSPACE_GB << 30)
    config.set_flag(trt.BuilderFlag.INT8)
    config.set_flag(trt.BuilderFlag.FP16)
    config.int8_calibrator = calibrator

    plan = builder.build_serialized_network(network, config)
    if plan is None:
        summary = {"status": "BLOCKED", "error": "build_serialized_network returned None"}
        out = PHASE0 / "results/jetson/int8_smoke.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary))
        return 1

    engine_path = ENGINE_DIR / "j3_c2_int8_smoke.engine"
    engine_path.write_bytes(plan)
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": "c2",
        "calib_stems": stems,
        "cache_path": str(cache_path),
        "cache_exists": cache_path.is_file(),
        "cache_bytes": cache_path.stat().st_size if cache_path.is_file() else 0,
        "engine_path": str(engine_path),
        "engine_bytes": engine_path.stat().st_size,
        "trt_version": trt.__version__,
        "deprecation_warnings": "待核: 日志中 INT8 calibrator 弃用提示需人工查看 build 日志",
        "status": "OK",
    }
    out = PHASE0 / "results/jetson/int8_smoke.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
