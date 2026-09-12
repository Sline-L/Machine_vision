from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
FIRST_STAGE_WEIGHTS = ROOT / "runs" / "gear_yolo26n_496train_50val_fixed" / "weights" / "best.pt"
DATA_CONFIG = ROOT / "dataset_defects" / "temp_second_model_140" / "data.yaml"


def main() -> None:
    if not FIRST_STAGE_WEIGHTS.exists():
        raise FileNotFoundError(FIRST_STAGE_WEIGHTS)
    if not DATA_CONFIG.exists():
        raise FileNotFoundError(DATA_CONFIG)

    model = YOLO(FIRST_STAGE_WEIGHTS)
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
        name="defect_yolo26n_140_v1_gpu",
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
