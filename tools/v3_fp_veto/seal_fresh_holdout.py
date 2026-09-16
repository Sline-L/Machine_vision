"""Seal a fresh Scratch holdout without exploratory inspection.

Enumerates files, records ids/hashes/labels required for scoring, writes
scratch-holdout.v1. Does not print label histograms or sample contents.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from holdout.seal_holdout import seal_holdout  # noqa: E402

CANDIDATE_COMMIT = "e8b2b0fda2af2c9c8c697d4655d527947381377a"
FORBIDDEN_TOKENS = ("test_scratch",)


def seal_fresh_holdout(
    images_dir: Path,
    labels_path: Path,
    *,
    dataset_id: str,
    source_description: str,
    output: Path,
    candidate_commit: str = CANDIDATE_COMMIT,
    adjudicator_commit: str | None = None,
) -> dict:
    images_dir = Path(images_dir)
    lowered = str(images_dir).replace("\\", "/").lower()
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            raise SystemExit(f"refusing to seal consumed/diagnostic path containing {token}")
    manifest = seal_holdout(
        images_dir,
        labels_path,
        dataset_id=dataset_id,
        source_description=source_description,
        output=output,
    )
    manifest["candidate_commit"] = candidate_commit
    manifest["adjudicator_commit"] = adjudicator_commit
    manifest["schema_version"] = "scratch-holdout.v1"
    manifest["purpose"] = "fix evaluation population before scoring; not EDA"
    manifest["fresh_holdout_status"] = "SEALED_UNSCORED"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sha_path = Path(str(output) + ".sha256")
    sha_path.write_text(manifest["dataset_sha256"] + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seal fresh holdout (no EDA)")
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-description", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--adjudicator-commit", default="")
    args = parser.parse_args(argv)
    manifest = seal_fresh_holdout(
        args.images,
        args.labels,
        dataset_id=args.dataset_id,
        source_description=args.source_description,
        output=args.output,
        adjudicator_commit=args.adjudicator_commit or None,
    )
    # Minimal confirmation only: identity + counts needed to know the set is fixed.
    print(
        json.dumps(
            {
                "dataset_id": manifest["dataset_id"],
                "dataset_sha256": manifest["dataset_sha256"],
                "sample_count": len(manifest["images"]),
                "sealed_at": manifest.get("sealed_at") or datetime.now(timezone.utc).isoformat(),
                "fresh_holdout_status": "SEALED_UNSCORED",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
