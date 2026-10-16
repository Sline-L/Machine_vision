#!/usr/bin/env python3
"""One-shot probe for detector_head.md (no images saved)."""
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from ultralytics import YOLO

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
onnx_path = REPO / "experiments/phase0/engines/onnx/detector.onnx"
weights = REPO / "model/model2/detector.pt"

yolo = YOLO(str(weights), task="detect")
last = yolo.model.model[-1]
info = {
    "weights": str(weights),
    "end2end_attr": bool(getattr(yolo.model, "end2end", False)),
    "last_module_type": type(last).__name__,
    "last_module_str": str(last)[:500],
    "names": yolo.names,
}
sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
inp = sess.get_inputs()[0]
out = sess.get_outputs()[0]
dummy = np.random.randint(0, 255, (1, 3, 960, 960), dtype=np.uint8).astype(np.float32) / 255.0
raw = sess.run(None, {inp.name: dummy})[0]
info["onnx_input_name"] = inp.name
info["onnx_input_shape"] = inp.shape
info["onnx_output_name"] = out.name
info["onnx_output_shape"] = list(raw.shape)
if raw.ndim == 3 and raw.shape[1] >= 5:
    cls = raw[:, 4:, :]
    info["onnx_max_conf_rule"] = "max over output[:, 4:, :] (class channels)"
    info["onnx_sample_max_conf"] = float(cls.max())
print(json.dumps(info, indent=2))
