#!/usr/bin/env python3
"""Write results/env/pc_env.json (P1 env record)."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def pkg_version(name: str) -> str | None:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", None)
    except Exception:
        return None


def main() -> None:
    import torch

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    driver = None
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            text=True,
            timeout=10,
        )
        driver = out.strip().splitlines()[0]
    except Exception:
        pass

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "torch": torch.__version__,
        "torchvision": pkg_version("torchvision"),
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": gpu_name,
        "nvidia_driver": driver,
        "numpy": pkg_version("numpy"),
        "opencv": pkg_version("cv2"),
        "Pillow": pkg_version("PIL"),
        "onnx": pkg_version("onnx"),
        "onnxruntime": pkg_version("onnxruntime"),
        "ultralytics": pkg_version("ultralytics"),
        "conda_env": Path(sys.prefix).name,
        "conda_prefix": sys.prefix,
    }
    out = REPO_ROOT / "experiments/phase0/results/env/pc_env.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
