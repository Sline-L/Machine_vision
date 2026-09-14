"""Model artifact contract: Dataset repo produces a bundle; GearPro only consumes it."""

from pathlib import Path
import json

SCHEMA_VERSION = "runtime-bundle.v1"
KNOWN_FAMILIES = ("scratch_v5",)


class BundleError(ValueError):
    pass


def _read_json(path):
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BundleError(f"找不到 bundle 文件：{path}") from None
    except json.JSONDecodeError as exc:
        raise BundleError(f"bundle JSON 无效：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BundleError(f"bundle 必须是对象：{path}")
    return payload


def manifest_path_for(config_path):
    config_path = Path(config_path)
    sibling = config_path.parent / "manifest.json"
    return sibling if sibling.is_file() else None


def load_runtime_bundle(config_path, require_manifest=False):
    """Load inference_config plus optional supply-chain manifest.

    GearPro must not read dataset_defects, runs/, or training scripts.
    """
    from .scratch_v5 import load_model2_config

    config_path = Path(config_path).expanduser().resolve()
    config = load_model2_config(config_path)
    manifest_path = manifest_path_for(config_path)
    if manifest_path is None:
        if require_manifest:
            raise BundleError(f"缺少 runtime bundle manifest：{config_path.parent / 'manifest.json'}")
        return {
            "schema_version": SCHEMA_VERSION,
            "bundle_id": config.get("version"),
            "task": "scratch_detection",
            "model_family": config.get("version"),
            "config": config,
            "manifest": None,
            "manifest_path": None,
        }
    manifest = _read_json(manifest_path)
    _validate_manifest(manifest, config, config_path.parent)
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": manifest["bundle_id"],
        "task": manifest["task"],
        "model_family": manifest["model_family"],
        "config": config,
        "manifest": manifest,
        "manifest_path": manifest_path,
    }


def _validate_manifest(manifest, config, bundle_dir):
    schema = manifest.get("schema_version") or SCHEMA_VERSION
    if schema != SCHEMA_VERSION:
        raise BundleError(f"不支持的 bundle schema：{schema}")
    for key in ("bundle_id", "task", "model_family", "artifacts", "evaluation"):
        if not manifest.get(key):
            raise BundleError(f"manifest 缺少 {key}")
    family = manifest["model_family"]
    if family not in KNOWN_FAMILIES:
        raise BundleError(f"未知 model_family：{family}")
    if family != config.get("version"):
        raise BundleError("manifest.model_family 与 inference_config.version 不一致")
    if family == "scratch_v5" and manifest.get("task") != "scratch_detection":
        raise BundleError("scratch_v5 的 task 必须是 scratch_detection")

    evaluation = manifest["evaluation"]
    if not isinstance(evaluation, dict):
        raise BundleError("evaluation 必须是对象")
    if "validation" not in evaluation or "locked_test" not in evaluation:
        raise BundleError("evaluation 必须分开 validation 与 locked_test，不能混成单一 recall")
    locked = evaluation["locked_test"]
    if isinstance(locked, dict) and locked.get("locked") is False:
        raise BundleError("locked_test.locked 必须为 true")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise BundleError("manifest.artifacts 不能为空")
    expected_names = {Path(item["weights"]).name for item in [*config["classifiers"], config["detector"]]}
    for name, meta in artifacts.items():
        path = bundle_dir / name
        if not path.is_file():
            raise BundleError(f"bundle 缺少产物：{name}")
        if name not in expected_names:
            raise BundleError(f"manifest 产物 {name} 不在 inference_config 中")
        listed = str((meta or {}).get("sha256") or "").lower()
        configured = None
        for item in [*config["classifiers"], config["detector"]]:
            if Path(item["weights"]).name == name:
                configured = str(item.get("sha256") or "").lower()
                break
        if listed and configured and listed != configured:
            raise BundleError(f"{name} 的 manifest SHA 与 inference_config 不一致")
    missing = expected_names - set(artifacts)
    if missing:
        raise BundleError("manifest 未覆盖全部权重：" + "、".join(sorted(missing)))
