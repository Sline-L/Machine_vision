from __future__ import annotations

import csv
import itertools
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from train_binary_defect_v4 import (
    OUTPUT,
    WORK,
    Experiment,
    apply_temperature,
    binary_auc,
    binary_label,
    choose_threshold,
    evaluate_probabilities,
    load_samples,
    predict,
    save_confusion,
)


def fuse(matrix: np.ndarray, mode: str) -> np.ndarray:
    if mode == "mean":
        return matrix.mean(axis=0)
    if mode == "max":
        return matrix.max(axis=0)
    if mode == "rank_mean":
        ranks = np.empty_like(matrix)
        for row_index, row in enumerate(matrix):
            order = np.argsort(row)
            ranks[row_index, order] = np.linspace(0.0, 1.0, len(row))
        return ranks.mean(axis=0)
    raise ValueError(mode)


def main() -> None:
    samples = load_samples()
    assignments = {row["stem"]: row["split"] for row in csv.DictReader((WORK / "split_manifest.csv").open(encoding="utf-8"))}
    val_samples = [sample for sample in samples if assignments[sample.stem] == "val"]
    test_samples = [sample for sample in samples if assignments[sample.stem] == "test"]
    labels = [binary_label(sample) for sample in val_samples]
    rows = [row for row in json.loads((OUTPUT / "leaderboard.json").read_text(encoding="utf-8")) if "operating_points" in row]
    rows.sort(key=lambda row: (row["auprc"], row["operating_points"]["0.3"]["recall"]), reverse=True)

    # Keep strong, architecturally diverse candidates. Limiting the pool reduces
    # validation-set overfitting while still giving the ensemble useful diversity.
    selected = []
    family_counts: dict[str, int] = {}
    for row in rows:
        family = row["family"]
        if family_counts.get(family, 0) >= 3:
            continue
        selected.append(row)
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(selected) == 8:
            break

    cache_dir = OUTPUT / "ensemble_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    val_probabilities: dict[str, np.ndarray] = {}
    for row in selected:
        cache = cache_dir / f"{row['name']}_val.npy"
        if cache.exists():
            probabilities = np.load(cache)
        else:
            experiment = Experiment(row["name"], row["family"], int(row["size"]), float(row["defect_weight"]), int(row["epochs"]), int(row["seed"]))
            raw = predict(Path(row["weights"]), experiment, val_samples, row["tta"])
            probabilities = np.asarray(apply_temperature(raw, float(row["temperature"])))
            np.save(cache, probabilities)
        val_probabilities[row["name"]] = probabilities

    candidates = []
    for count in (1, 2, 3, 4):
        for members in itertools.combinations(selected, count):
            matrix = np.stack([val_probabilities[row["name"]] for row in members])
            for mode in (("mean",) if count == 1 else ("mean", "max", "rank_mean")):
                probabilities = fuse(matrix, mode)
                point = choose_threshold(labels, probabilities.tolist(), 0.30)
                auroc, auprc = binary_auc(labels, probabilities.tolist())
                candidates.append({
                    "members": [row["name"] for row in members],
                    "fusion": mode,
                    "operating_point": point,
                    "auroc": auroc,
                    "auprc": auprc,
                    "probabilities": probabilities,
                })
    candidates.sort(key=lambda item: (
        item["operating_point"]["fpr"] <= 0.30,
        item["operating_point"]["recall"],
        -item["operating_point"]["fpr"],
        item["auprc"],
        -len(item["members"]),
    ), reverse=True)
    winner = candidates[0]
    operating_points = {
        str(cap): choose_threshold(labels, winner["probabilities"].tolist(), cap)
        for cap in (0.10, 0.20, 0.30, 0.50, 1.0)
    }
    member_rows = [next(row for row in selected if row["name"] == name) for name in winner["members"]]

    final_dir = OUTPUT / "final_ensemble"
    final_dir.mkdir(parents=True, exist_ok=True)
    models = []
    test_matrix = []
    for row in member_rows:
        destination = final_dir / f"{row['name']}.pt"
        shutil.copy2(row["weights"], destination)
        models.append({
            "name": row["name"], "family": row["family"], "weights": str(destination),
            "imgsz": int(row["size"]), "tta": row["tta"], "temperature": float(row["temperature"]),
        })
        experiment = Experiment(row["name"], row["family"], int(row["size"]), float(row["defect_weight"]), int(row["epochs"]), int(row["seed"]))
        raw = predict(Path(row["weights"]), experiment, test_samples, row["tta"])
        test_matrix.append(apply_temperature(raw, float(row["temperature"])))
    test_probabilities = fuse(np.asarray(test_matrix), winner["fusion"]).tolist()
    threshold = float(winner["operating_point"]["threshold"])
    test_metrics = evaluate_probabilities(test_samples, test_probabilities, threshold)

    config = {
        "models": models,
        "fusion": winner["fusion"],
        "default_threshold": threshold,
        "operating_points": operating_points,
        "high_sensitivity_threshold": operating_points["1.0"]["threshold"],
        "validation_operating_point": winner["operating_point"],
        "decision": "REJECT when fused defect_probability >= threshold",
    }
    (OUTPUT / "inference_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    serializable = [{key: value for key, value in item.items() if key != "probabilities"} for item in candidates[:50]]
    (OUTPUT / "ensemble_leaderboard.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    predictions = []
    visual_dir = OUTPUT / "test_predictions_ensemble"
    visual_dir.mkdir(parents=True, exist_ok=True)
    for sample, probability in zip(test_samples, test_probabilities):
        decision = "reject" if probability >= threshold else "pass"
        predictions.append({"stem": sample.stem, "truth": "defect" if binary_label(sample) else "normal", "source_category": sample.category, "view": sample.view, "defect_probability": probability, "decision": decision, "correct": int((probability >= threshold) == bool(binary_label(sample)))})
        with Image.open(sample.image) as opened:
            image = opened.convert("RGB")
        ImageDraw.Draw(image).text((8, 8), f"{decision.upper()} defect={probability:.3f} threshold={threshold:.3f}", fill=(255, 30, 30) if decision == "reject" else (0, 170, 40))
        image.save(visual_dir / f"{sample.stem}.jpg", quality=95)
    with (OUTPUT / "test_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=predictions[0].keys())
        writer.writeheader()
        writer.writerows(predictions)
    save_confusion(test_metrics, OUTPUT / "confusion_matrix.png")
    report = {
        "selection": "validation-only ensemble search",
        "ensemble": {key: value for key, value in winner.items() if key != "probabilities"},
        "test": test_metrics,
        "target": {"recall": 0.95, "fpr_max": 0.30},
        "target_met": test_metrics["overall"]["recall"] >= 0.95 and test_metrics["overall"]["fpr"] <= 0.30,
    }
    (OUTPUT / "final_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
