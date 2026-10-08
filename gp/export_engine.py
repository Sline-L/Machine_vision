"""Export Model1 from `.pt` to TensorRT `.engine` on the target Jetson."""

from pathlib import Path
import shutil

from .launch import EXPORTS, PROJECT_ROOT

DEFAULT_SOURCE = PROJECT_ROOT / "model" / "model1.pt"
DEFAULT_DEST = EXPORTS / "model1.engine"


def export_locator_engine(source=DEFAULT_SOURCE, dest=DEFAULT_DEST, imgsz=640):
    """Build an FP16 TensorRT engine for the gear locator.

    Ultralytics still writes a temporary ONNX file while compiling. That file is
    deleted afterwards; inference only uses `.pt` and `.engine`.
    """
    import torch
    from ultralytics import YOLO

    source = Path(source).expanduser().resolve()
    dest = Path(dest).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到定位模型：{source}")
    if not torch.cuda.is_available():
        raise RuntimeError("导出 engine 需要 CUDA，请在 Jetson NX 上运行 export_engine.py")

    dest.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(source), task="detect")
    exported = Path(
        model.export(
            format="engine",
            imgsz=imgsz,
            batch=1,
            half=True,
            dynamic=False,
            nms=False,
            device=0,
            workspace=4,
        )
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(exported), dest)

    leftovers = {
        source.with_suffix(".onnx"),
        exported.with_suffix(".onnx"),
        Path(str(exported) + ".onnx"),
    }
    for leftover in leftovers:
        if leftover.is_file():
            leftover.unlink()
    return dest


SPECIALIST_EXPORTS = EXPORTS / "specialists"
BUNDLE_CONFIGS = {
    "scratch_v5": PROJECT_ROOT / "model" / "model2" / "inference_config.json",
    "missing_hole_v1": PROJECT_ROOT / "model" / "missing_hole_v1" / "inference_config.json",
}


def _load_bundle_runtime(config_path):
    """Load the production runtime on CPU so the exported modules match it exactly."""
    import json

    version = json.loads(Path(config_path).read_text(encoding="utf-8")).get("version")
    if version == "scratch_v5":
        from .scratch_v5 import ScratchV5Runtime as Runtime
    elif version == "missing_hole_v1":
        from .missing_hole import MissingHoleRuntime as Runtime
    else:
        raise ValueError(f"不支持的专项模型版本：{version}")
    return Runtime(config_path, device="cpu", warmup=False)


def dla_layer_report(onnx_file, dla_core, half=True):
    """Count layers TensorRT can place on DLA; the rest fall back to GPU."""
    import tensorrt as trt

    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, logger)
    if not parser.parse_from_file(str(onnx_file)):
        raise RuntimeError(f"无法解析 ONNX：{onnx_file}")
    config = builder.create_builder_config()
    if half:
        config.set_flag(trt.BuilderFlag.FP16)
    config.default_device_type = trt.DeviceType.DLA
    config.DLA_core = int(dla_core)
    config.set_flag(trt.BuilderFlag.GPU_FALLBACK)
    fallback = {}
    eligible = 0
    for index in range(network.num_layers):
        layer = network.get_layer(index)
        if config.can_run_on_DLA(layer):
            eligible += 1
        else:
            kind = str(layer.type).split(".")[-1]
            fallback[kind] = fallback.get(kind, 0) + 1
    return {"layers": network.num_layers, "dla_eligible": eligible, "gpu_fallback_types": fallback}


def _export_classifier(model, size, onnx_file, engine_file, dla_core, workspace):
    import torch
    from ultralytics.utils.export.engine import onnx2engine, torch2onnx

    model = model.to("cuda:0").eval()
    dummy = torch.zeros((1, 3, size, size), device="cuda:0")
    torch2onnx(model, dummy, str(onnx_file), opset=17, input_names=["images"], output_names=["logits"])
    report = None if dla_core is None else dla_layer_report(onnx_file, dla_core)
    onnx2engine(
        str(onnx_file),
        str(engine_file),
        workspace=workspace,
        half=True,
        shape=(1, 3, size, size),
        dla=dla_core,
        metadata=None,
    )
    model.to("cpu")
    return report


def _export_detector(item, build_dir, engine_file, dla_core, dynamic, workspace):
    from ultralytics import YOLO

    # Export from a copy so Ultralytics never writes next to the tracked `.pt`.
    source = build_dir / Path(item["weights"]).name
    shutil.copy2(item["weights"], source)
    exported = Path(
        YOLO(str(source), task="detect").export(
            format="engine",
            imgsz=int(item["imgsz"]),
            batch=1,
            half=True,
            dynamic=dynamic,
            nms=False,
            device=0 if dla_core is None else f"dla:{dla_core}",
            # Ultralytics sizes the dynamic profile as imgsz * max(2, workspace).
            workspace=None if dynamic else workspace,
        )
    )
    shutil.move(str(exported), engine_file)


def export_specialist_engines(
    config_path,
    dest_root=SPECIALIST_EXPORTS / "fp16",
    classifier_dla_cores=(),
    detector_dla_core=None,
    dynamic_detector=False,
    workspace=4,
    keep_onnx=False,
):
    """Build FP16 engines for one specialist bundle under `dest_root/<version>/`.

    `classifier_dla_cores` assigns classifier i to core i % len(cores); empty
    keeps classifiers on the GPU. A static detector engine letterboxes to a
    square input while `.pt` uses the minimal rectangle; `dynamic_detector`
    keeps the `.pt` letterbox at some engine speed cost.
    """
    import datetime
    import json
    import platform

    import tensorrt as trt
    import torch

    from .specialist_engines import (
        MANIFEST_NAME,
        MANIFEST_SCHEMA,
        bundle_models,
        engine_filename,
        sha256_file,
    )

    if not torch.cuda.is_available():
        raise RuntimeError("导出 engine 需要 CUDA，请在目标设备上运行")
    runtime = _load_bundle_runtime(config_path)
    config = runtime.config
    modules = {str(item["name"]): model for item, model in runtime.classifiers}
    dest = Path(dest_root).expanduser().resolve() / config["version"]
    build_dir = dest / "_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    entries = {}
    try:
        classifier_index = 0
        for item, kind in bundle_models(config):
            name = str(item["name"])
            engine_file = dest / engine_filename(item)
            if engine_file.exists():
                engine_file.unlink()
            entry = {
                "kind": kind,
                "source_sha256": str(item["sha256"]).lower(),
                "imgsz": int(item["imgsz"]),
                "precision": "fp16",
                "dla_core": None,
            }
            if kind == "classifier":
                cores = list(classifier_dla_cores)
                dla_core = cores[classifier_index % len(cores)] if cores else None
                classifier_index += 1
                onnx_file = build_dir / f"{name}.onnx"
                entry["dla_core"] = dla_core
                entry["dla_layers"] = _export_classifier(
                    modules[name], int(item["imgsz"]), onnx_file, engine_file, dla_core, workspace
                )
                if keep_onnx:
                    shutil.copy2(onnx_file, dest / onnx_file.name)
            else:
                entry["dla_core"] = detector_dla_core
                entry["dynamic"] = bool(dynamic_detector)
                _export_detector(item, build_dir, engine_file, detector_dla_core, dynamic_detector, workspace)
            entry["engine_sha256"] = sha256_file(engine_file)
            entries[name] = entry
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "bundle_version": config["version"],
        "bundle_config": str(config["config_path"]),
        "bundle_config_sha256": sha256_file(config["config_path"]),
        "tensorrt": trt.__version__,
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "machine": platform.machine(),
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "models": entries,
    }
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def _parse_cores(text):
    if not text:
        return ()
    cores = tuple(int(value) for value in text.split(","))
    if any(core not in (0, 1) for core in cores):
        raise ValueError("DLA 核心只能是 0 或 1")
    return cores


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="python -m gp.export_engine", description="在目标设备上编译 TensorRT engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("locator", help="定位模型 model1.pt → .cache/exports/model1.engine")
    specialists = sub.add_parser("specialists", help="Scratch V5 / Missing Hole V1 六个专项模型 → FP16 engine")
    specialists.add_argument("--bundle", choices=["all", *BUNDLE_CONFIGS], default="all")
    specialists.add_argument("--tag", help="输出子目录名，默认 fp16 或 fp16-dla")
    specialists.add_argument("--dest-root", type=Path, default=SPECIALIST_EXPORTS)
    specialists.add_argument("--classifier-dla", default="", help="分类器 DLA 核心，如 0,1；默认留在 GPU")
    specialists.add_argument("--detector-dla", type=int, choices=[0, 1], help="检测器也放 DLA（YOLO 大量层会回退 GPU）")
    specialists.add_argument("--dynamic-detector", action="store_true", help="动态输入，保持与 .pt 相同的矩形 letterbox")
    specialists.add_argument("--workspace", type=float, default=4, help="TensorRT workspace GB")
    specialists.add_argument("--keep-onnx", action="store_true", help="保留分类器中间 ONNX（仅用于排查）")
    args = parser.parse_args(argv)
    try:
        if args.command == "locator":
            print(f"已生成 {export_locator_engine()}")
            return 0
        cores = _parse_cores(args.classifier_dla)
        tag = args.tag or ("fp16-dla" if cores or args.detector_dla is not None else "fp16")
        names = list(BUNDLE_CONFIGS) if args.bundle == "all" else [args.bundle]
        for name in names:
            path = export_specialist_engines(
                BUNDLE_CONFIGS[name],
                dest_root=args.dest_root / tag,
                classifier_dla_cores=cores,
                detector_dla_core=args.detector_dla,
                dynamic_detector=args.dynamic_detector,
                workspace=args.workspace,
                keep_onnx=args.keep_onnx,
            )
            print(f"已生成 {path}")
        print(f"基准测试：python -m gp.bench run --engines {args.dest_root / tag} ...")
    except Exception as exc:
        print(f"导出失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
