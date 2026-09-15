"""CLI for vision v2 val-only Pareto evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gp.config import PROJECT_ROOT
from edgemedic.vision_v2_evaluator import run_evaluation


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vision v2 lightweight val Pareto (exploratory)")
    parser.add_argument(
        "--full-csv",
        type=Path,
        default=PROJECT_ROOT / "final" / "val_predictions.csv",
    )
    parser.add_argument(
        "--cls-csv",
        type=Path,
        default=PROJECT_ROOT / "docs" / "capability-extraction" / "configs" / "classifier_only_mean.val_predictions.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "results" / "lightweight_capability_v2" / "val_pareto",
    )
    args = parser.parse_args(argv)
    payload = run_evaluation(args.full_csv, args.cls_csv, args.out)
    print(json.dumps({"out": str(args.out), "primary": payload.get("primary_candidate"), "n": payload["n_val"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
