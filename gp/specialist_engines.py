"""TensorRT engines for the Scratch V5 / Missing Hole V1 specialist models.

Engines are board-specific build products under `.cache/exports/specialists/`.
Each bundle directory holds one `<model name>.engine` per model plus a
`manifest.json` that binds every engine to the SHA256 of its source `.pt`, so a
stale engine cannot silently replace a retrained model.
"""

import hashlib
import json
from pathlib import Path
import time

MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "gearpro-specialist-engines.v1"


def bundle_models(config):
    """Return `(item, kind)` for every model of a loaded bundle configuration."""
    if config.get("version") == "scratch_v5":
        return [(item, "classifier") for item in config["classifiers"]] + [(config["detector"], "detector")]
    if config.get("version") == "missing_hole_v1":
        return [(item, item["kind"]) for item in config["models"]]
    raise ValueError(f"不支持的专项模型版本：{config.get('version')}")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def engine_filename(item):
    name = str(item.get("name", ""))
    if not name or any(char in name for char in '/\\:'):
        raise ValueError(f"模型名称不能作为 engine 文件名：{name!r}")
    return f"{name}.engine"


def verify_manifest(directory, config, tensorrt_version=None, check_hashes=True):
    """Validate an engine bundle against the loaded `.pt` bundle configuration.

    Returns the manifest model entries keyed by model name. `tensorrt_version`
    is the installed TensorRT version; pass None to skip that check (tests).
    """
    directory = Path(directory)
    path = directory / MANIFEST_NAME
    if not path.is_file():
        raise FileNotFoundError(f"找不到专项 engine 清单：{path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"专项 engine 清单版本不支持：{manifest.get('schema')}")
    if manifest.get("bundle_version") != config.get("version"):
        raise ValueError("专项 engine 清单与模型包版本不一致")
    built_with = manifest.get("tensorrt")
    if tensorrt_version is not None and built_with != tensorrt_version:
        raise ValueError(f"engine 由 TensorRT {built_with} 编译，当前为 {tensorrt_version}，请在本机重新导出")
    entries = manifest.get("models") or {}
    for item, kind in bundle_models(config):
        name = str(item.get("name", ""))
        entry = entries.get(name)
        if entry is None:
            raise ValueError(f"engine 清单缺少模型：{name}")
        if entry.get("kind") != kind:
            raise ValueError(f"engine 清单模型种类不一致：{name}")
        if str(entry.get("source_sha256", "")).lower() != str(item.get("sha256", "")).lower():
            raise ValueError(f"engine 与当前 .pt 权重不一致，请重新导出：{name}")
        if int(entry.get("imgsz", 0)) != int(item["imgsz"]):
            raise ValueError(f"engine 输入尺寸与配置不一致：{name}")
        engine = directory / engine_filename(item)
        if not engine.is_file():
            raise FileNotFoundError(f"找不到 engine：{engine}")
        if check_hashes and sha256_file(engine) != entry.get("engine_sha256"):
            raise ValueError(f"engine 文件校验失败：{engine.name}")
    return entries


class EngineBundle:
    """Verified engine directory for one specialist bundle."""

    def __init__(self, directory, entries, device):
        self.directory = Path(directory)
        self.entries = entries
        self.device = device

    def engine_path(self, item):
        return self.directory / engine_filename(item)

    def classifier(self, item):
        entry = self.entries[str(item["name"])]
        return TensorRTClassifier(self.engine_path(item), self.device, entry.get("dla_core"))


def load_engine_bundle(directory, config, device):
    import tensorrt as trt

    if getattr(device, "type", str(device)) != "cuda":
        raise ValueError("TensorRT engine 只能在 CUDA 设备上运行")
    entries = verify_manifest(directory, config, tensorrt_version=trt.__version__)
    return EngineBundle(directory, entries, device)


class PendingLogits:
    """Logits of one asynchronous classifier run."""

    def __init__(self, output, start, end, enqueued):
        self.output = output
        self.start = start
        self.end = end
        self.enqueued = enqueued
        self.device_ms = 0.0

    def wait(self):
        self.end.synchronize()
        self.device_ms = float(self.start.elapsed_time(self.end))
        return self.output

    def prepare_ms(self, started):
        """Host-side preprocessing time before this job was enqueued."""
        return (self.enqueued - started) * 1000


class TensorRTClassifier:
    """Single-input/single-output classifier engine fed with torch CUDA tensors.

    Calling the object behaves like the `.pt` module (`model(tensor)` returns
    logits). `enqueue` runs it on a private stream, which lets DLA or GPU
    classifier work overlap the YOLO detector. Requires TensorRT >= 8.5.
    """

    def __init__(self, path, device, dla_core=None):
        import tensorrt as trt
        import torch

        self.torch = torch
        self.path = Path(path)
        self._logger = trt.Logger(trt.Logger.WARNING)
        self._runtime = trt.Runtime(self._logger)
        if dla_core is not None:
            self._runtime.DLA_core = int(dla_core)
        self.engine = self._runtime.deserialize_cuda_engine(self.path.read_bytes())
        if self.engine is None:
            raise RuntimeError(f"无法反序列化 engine：{self.path}")
        self.context = self.engine.create_execution_context()
        names = [self.engine.get_tensor_name(index) for index in range(self.engine.num_io_tensors)]
        inputs = [name for name in names if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT]
        outputs = [name for name in names if name not in inputs]
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError(f"分类器 engine 必须只有一个输入和一个输出：{self.path.name}")
        self.input_name, self.output_name = inputs[0], outputs[0]
        self.input_shape = tuple(self.engine.get_tensor_shape(self.input_name))
        dtypes = {trt.DataType.FLOAT: torch.float32, trt.DataType.HALF: torch.float16}
        self.input_dtype = dtypes[self.engine.get_tensor_dtype(self.input_name)]
        self.output = torch.empty(
            tuple(self.engine.get_tensor_shape(self.output_name)),
            dtype=dtypes[self.engine.get_tensor_dtype(self.output_name)],
            device=device,
        )
        self.context.set_tensor_address(self.output_name, self.output.data_ptr())
        self.stream = torch.cuda.Stream(device=device)

    def enqueue(self, tensor):
        torch = self.torch
        if tuple(tensor.shape) != self.input_shape:
            raise ValueError(f"engine 输入形状应为 {self.input_shape}，实际为 {tuple(tensor.shape)}")
        tensor = tensor.to(self.input_dtype).contiguous()
        self.stream.wait_stream(torch.cuda.current_stream(tensor.device))
        tensor.record_stream(self.stream)
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        enqueued = time.perf_counter()
        with torch.cuda.stream(self.stream):
            start.record()
            self.context.set_tensor_address(self.input_name, tensor.data_ptr())
            if not self.context.execute_async_v3(self.stream.cuda_stream):
                raise RuntimeError(f"TensorRT 推理失败：{self.path.name}")
            output = self.output.float()
            if output.data_ptr() == self.output.data_ptr():
                output = output.clone()
            end.record()
        return PendingLogits(output, start, end, enqueued)

    def __call__(self, tensor):
        return self.enqueue(tensor).wait()
