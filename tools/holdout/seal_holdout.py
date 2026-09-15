"""Seal a fresh Scratch-only holdout dataset (images + labels)."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seal_holdout(
    images_dir: Path,
    labels_path: Path,
    *,
    dataset_id: str,
    source_description: str,
    output: Path,
) -> dict:
    images_dir = Path(images_dir)
    labels_path = Path(labels_path)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(labels, dict):
        raise ValueError("labels must be a JSON object: {filename: 'scratch'|'normal'}")
    image_rows = []
    for path in sorted(images_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
            continue
        label = labels.get(path.name)
        if label not in {"scratch", "normal"}:
            raise ValueError(f"missing/invalid label for {path.name}")
        image_rows.append(
            {
                "file": path.name,
                "label": label,
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    if not image_rows:
        raise ValueError("no images found")
    positives = sum(1 for row in image_rows if row["label"] == "scratch")
    negatives = len(image_rows) - positives
    manifest = {
        "schema_version": "scratch-holdout.v1",
        "dataset_id": dataset_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_description": source_description,
        "images_dir": str(images_dir.resolve()),
        "labels_path": str(labels_path.resolve()),
        "images": image_rows,
        "positive_count": positives,
        "negative_count": negatives,
        "label_space": ["scratch", "normal"],
        "bbox_required": False,
        "sealed_at": None,
        "dataset_sha256": "",
    }
    body = dict(manifest)
    body["dataset_sha256"] = ""
    body["sealed_at"] = None
    digest = _sha256_text(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    manifest["dataset_sha256"] = digest
    manifest["sealed_at"] = datetime.now(timezone.utc).isoformat()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seal Scratch-only holdout manifest")
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path, help="JSON map filename->scratch|normal")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-description", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = seal_holdout(
        args.images,
        args.labels,
        dataset_id=args.dataset_id,
        source_description=args.source_description,
        output=args.output,
    )
    print(json.dumps({"dataset_id": manifest["dataset_id"], "dataset_sha256": manifest["dataset_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
