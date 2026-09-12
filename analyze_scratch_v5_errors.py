from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "outputs" / "scratch_v5" / "test_scratch"
ANNOTATIONS = ROOT / "dataset_defects" / "annotations" / "test_scratch"


def contact_sheet(rows: list[dict[str, str]], destination: Path) -> None:
    columns = 4
    cell_width, cell_height = 280, 250
    sheet = Image.new("RGB", (columns * cell_width, ((len(rows) + columns - 1) // columns) * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        path = Path(row["image"])
        with Image.open(path) as opened:
            original = opened.convert("RGB")
        xml_path = ANNOTATIONS / f"{path.stem}.xml"
        if xml_path.is_file():
            overlay = ImageDraw.Draw(original)
            for obj in ET.parse(xml_path).getroot().findall("object"):
                box = obj.find("bndbox")
                if box is None:
                    continue
                coordinates = tuple(float(box.findtext(name, "0")) for name in ("xmin", "ymin", "xmax", "ymax"))
                overlay.rectangle(coordinates, outline=(255, 0, 0), width=3)
        image = ImageOps.contain(original, (cell_width - 16, cell_height - 45))
        x, y = (index % columns) * cell_width, (index // columns) * cell_height
        sheet.paste(image, (x + (cell_width - image.width) // 2, y + 28))
        draw.text((x + 6, y + 6), f"{path.name}  p={float(row['scratch_probability']):.3f}", fill="black")
    sheet.save(destination, quality=95)


def main() -> None:
    with (RESULTS / "test_predictions.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        with Image.open(row["image"]) as opened:
            gray = np.asarray(opened.convert("L"), dtype=np.float32)
            row["width"], row["height"] = opened.size
        row["brightness_mean"] = float(gray.mean())
        row["contrast_std"] = float(gray.std())

    false_negatives = [row for row in rows if row["truth"] == "scratch" and row["prediction"] == "PASS"]
    false_positives = [row for row in rows if row["truth"] == "normal" and row["prediction"] == "REJECT"]
    contact_sheet(false_negatives, RESULTS / "false_negatives.jpg")
    contact_sheet(false_positives, RESULTS / "false_positives.jpg")

    groups = {}
    for name, subset in (
        ("true_positive", [row for row in rows if row["truth"] == "scratch" and row["prediction"] == "REJECT"]),
        ("false_negative", false_negatives),
        ("true_negative", [row for row in rows if row["truth"] == "normal" and row["prediction"] == "PASS"]),
        ("false_positive", false_positives),
    ):
        groups[name] = {
            "count": len(subset),
            "mean_width": float(np.mean([float(row["width"]) for row in subset])) if subset else None,
            "mean_height": float(np.mean([float(row["height"]) for row in subset])) if subset else None,
            "mean_brightness": float(np.mean([float(row["brightness_mean"]) for row in subset])) if subset else None,
            "mean_contrast": float(np.mean([float(row["contrast_std"]) for row in subset])) if subset else None,
            "mean_classifier_probability": float(np.mean([float(row["classifier_probability"]) for row in subset])) if subset else None,
            "mean_detector_probability": float(np.mean([float(row["detector_probability"]) for row in subset])) if subset else None,
        }
    (RESULTS / "error_analysis.json").write_text(json.dumps(groups, indent=2), encoding="utf-8")
    print(json.dumps(groups, indent=2))


if __name__ == "__main__":
    main()
