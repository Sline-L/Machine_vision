"""Detector score helpers for phase 0 (host-side max confidence)."""

from __future__ import annotations

import numpy as np
import torch


def detector_max_from_tensor(model, det_uint8_bchw: np.ndarray, device: torch.device) -> tuple[float, int]:
    """Letterboxed RGB uint8 BCHW -> max box conf (conf >= 0.001 count)."""
    hwc = np.transpose(det_uint8_bchw[0], (1, 2, 0))
    yolo_device = 0 if device.type == "cuda" else "cpu"
    results = model.predict(
        hwc,
        imgsz=hwc.shape[0],
        conf=0.001,
        iou=0.7,
        device=yolo_device,
        verbose=False,
    )
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return 0.0, 0
    conf = boxes.conf.detach().float().cpu().numpy().reshape(-1)
    return float(conf.max()), int((conf >= 0.001).sum())
