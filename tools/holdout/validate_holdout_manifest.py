"""Validate a sealed holdout manifest and optional duplicate/near-dup reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_manifest(manifest_path: Path, *, known_hash_dirs: list[Path] | None = None) -> dict:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    body = dict(manifest)
    listed = body.get("dataset_sha256")
    sealed_at = body.get("sealed_at")
    body["dataset_sha256"] = ""
    body["sealed_at"] = None
    expected = _sha256_text(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    if listed != expected:
        raise ValueError(f"manifest hash mismatch: listed={listed} expected={expected}")
    images_dir = Path(manifest["images_dir"])
    failures = []
    for row in manifest["images"]:
        image = images_dir / row["file"]
        if not image.is_file():
            failures.append(f"missing:{row['file']}")
            continue
        actual = _sha256_file(image)
        if actual != row["sha256"]:
            failures.append(f"changed:{row['file']}")
    if failures:
        raise ValueError("holdout integrity failed: " + ", ".join(failures[:20]))

    exact_dups = []
    known = {}
    for directory in known_hash_dirs or []:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for file_path in directory.rglob("*"):
            if file_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
                continue
            known[_sha256_file(file_path)] = str(file_path)
    for row in manifest["images"]:
        hit = known.get(row["sha256"])
        if hit:
            exact_dups.append({"file": row["file"], "known": hit})

    return {
        "ok": True,
        "dataset_id": manifest["dataset_id"],
        "dataset_sha256": listed,
        "sealed_at": sealed_at,
        "exact_hash_duplicates": exact_dups,
        "perceptual_duplicates": [],
        "notes": "perceptual hash reporting reserved; exact hash checked",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate sealed holdout manifest")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--known-dir", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    report = validate_manifest(args.manifest, known_hash_dirs=args.known_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
