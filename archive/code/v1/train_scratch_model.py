from __future__ import annotations

import argparse
from pathlib import Path

import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
FIRST_STAGE_WEIGHTS = ROOT / "runs" / "gear_yolo26n_496train_50val_fixed" / "weights" / "best.pt"
DATA_CONFIG = ROOT / "dataset_defects" / "temp_scratch_model_211_from_343" / "data.yaml"
RUN_NAME = "scratch_yolo26n_211_v1"


def check_inputs() -> YOLO:
    if not FIRST_STAGE_WEIGHTS.is_file():
        raise FileNotFoundError(FIRST_STAGE_WEIGHTS)
    if not DATA_CONFIG.is_file():
        raise FileNotFoundError(DATA_CONFIG)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; scratch training requires the configured NVIDIA GPU")

    model = YOLO(FIRST_STAGE_WEIGHTS)
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"Initial weights: {FIRST_STAGE_WEIGHTS}")
    print(f"Dataset: {DATA_CONFIG}")
    print("Target class: 0=scratch")
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the scratch-only second-stage detector.")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Validate CUDA, weights, and dataset without starting training.",
    )
    args = parser.parse_args()

    model = check_inputs()
    if args.preflight:
        print("Preflight passed; training was not started")
        return

    run_dir = ROOT / "runs" / RUN_NAME
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")

    model.train(
        data=str(DATA_CONFIG),
        epochs=100,
        patience=30,
        imgsz=960,
        batch=16,
        device=0,
        workers=4,
        cache="ram",
        project=str(ROOT / "runs"),
        name=RUN_NAME,
        exist_ok=False,
        pretrained=True,
        optimizer="AdamW",
        lr0=0.001,
        weight_decay=0.0005,
        close_mosaic=10,
        degrees=10.0,
        translate=0.05,
        scale=0.25,
        fliplr=0.5,
        flipud=0.5,
        mosaic=0.5,
        mixup=0.0,
        seed=42,
        deterministic=True,
        plots=True,
    )


if __name__ == "__main__":
    main()
