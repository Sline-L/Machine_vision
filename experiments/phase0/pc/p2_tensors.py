#!/usr/bin/env python3
"""P2: generate cls384 and det960 tensors + tensor_manifest.csv."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from torchvision import transforms

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.phase0.common.hash_util import sha256_file  # noqa: E402
from gp.scratch_v5 import square_rgb_image  # noqa: E402
from ultralytics.data.augment import LetterBox  # noqa: E402

CLS_SIZE = 384
DET_SIZE = 960


def load_roles(manifest_images: Path) -> list[dict[str, str]]:
    with manifest_images.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("role")]
    return rows


def cls_tensor_from_bgr(bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    image = square_rgb_image(rgb, CLS_SIZE)
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
    )
    tensor = transform(image).unsqueeze(0).numpy().astype(np.float32)
    return tensor


def det_tensor_from_bgr(bgr: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    letterbox = LetterBox((DET_SIZE, DET_SIZE), auto=False, scaleup=True)
    out = letterbox(image=rgb)
    h, w = rgb.shape[:2]
    r = min(DET_SIZE / h, DET_SIZE / w)
    new_unpad = (round(w * r), round(h * r))
    pad_x = int((DET_SIZE - new_unpad[0]) / 2)
    pad_y = int((DET_SIZE - new_unpad[1]) / 2)
    chw = np.transpose(out, (2, 0, 1))[None, ...].astype(np.uint8)
    return chw, float(r), pad_x, pad_y


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"G:/CODE/gp-dataset/dataset_defects/scratch_v5"),
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=REPO_ROOT / "experiments/phase0/results",
    )
    args = parser.parse_args()
    data_dir = REPO_ROOT / "experiments/phase0/data/tensors"
    data_dir.mkdir(parents=True, exist_ok=True)

    roles = load_roles(args.results_root / "pc/manifest_images.csv")
    manifest_rows: list[dict[str, str]] = []

    for idx, row in enumerate(roles):
        stem = row["stem"]
        split = row["split"]
        path = args.dataset_root / "images" / split / f"{stem}.jpg"
        bgr = cv2.imread(str(path))
        if bgr is None:
            print(f"BLOCKED: missing image {path}", file=sys.stderr)
            return 1

        cls = cls_tensor_from_bgr(bgr)
        cls_path = data_dir / f"{stem}_cls384.npy"
        np.save(cls_path, cls)

        det, scale, pad_x, pad_y = det_tensor_from_bgr(bgr)
        det_path = data_dir / f"{stem}_det960.npy"
        np.save(det_path, det)

        for kind, arr, fpath in (
            ("cls384", cls, cls_path),
            ("det960", det, det_path),
        ):
            manifest_rows.append(
                {
                    "stem": stem,
                    "kind": kind,
                    "path": str(fpath.relative_to(REPO_ROOT)).replace("\\", "/"),
                    "sha256": sha256_file(fpath),
                    "shape": "x".join(str(x) for x in arr.shape),
                    "dtype": str(arr.dtype),
                    "letterbox_scale": repr(scale) if kind == "det960" else "",
                    "pad_x": str(pad_x) if kind == "det960" else "",
                    "pad_y": str(pad_y) if kind == "det960" else "",
                    "subset": row["role"],
                }
            )
        if (idx + 1) % 50 == 0:
            print(f"P2 progress {idx + 1}/{len(roles)}")

    manifest_path = data_dir / "tensor_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stem",
                "kind",
                "path",
                "sha256",
                "shape",
                "dtype",
                "letterbox_scale",
                "pad_x",
                "pad_y",
                "subset",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    # determinism: re-hash cls files
    dup = 0
    for row in manifest_rows:
        if row["kind"] != "cls384":
            continue
        p = REPO_ROOT / row["path"]
        if sha256_file(p) != row["sha256"]:
            dup += 1

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n_stems": len(roles),
        "n_files": len(manifest_rows),
        "sha_recheck_mismatch": dup,
        "nan_cls": sum(1 for r in manifest_rows if r["kind"] == "cls384" and "nan" in r["sha256"].lower()),
        "status": "OK" if len(roles) == 514 and len(manifest_rows) == 1028 and dup == 0 else "BLOCKED",
    }
    out = args.results_root / "pc/p2_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
