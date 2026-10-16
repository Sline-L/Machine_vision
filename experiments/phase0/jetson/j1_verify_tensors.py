#!/usr/bin/env python3
"""J1: verify transferred tensors against tensor_manifest.csv."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.phase0.common.hash_util import sha256_file  # noqa: E402


def main() -> int:
    data_dir = REPO / "experiments/phase0/data/tensors"
    manifest = data_dir / "tensor_manifest.csv"
    mismatches = []
    missing = []
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            path = REPO / row["path"]
            if not path.is_file():
                missing.append(row["path"])
                continue
            digest = sha256_file(path)
            if digest != row["sha256"]:
                mismatches.append({"path": row["path"], "expected": row["sha256"], "got": digest})
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n_manifest_rows": sum(1 for _ in open(manifest, encoding="utf-8")) - 1,
        "missing": len(missing),
        "mismatch": len(mismatches),
        "status": "OK" if not missing and not mismatches else "BLOCKED",
        "sample_mismatch": mismatches[:5],
        "sample_missing": missing[:5],
    }
    out = REPO / "experiments/phase0/results/jetson/j1_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
