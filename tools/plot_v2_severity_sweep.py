#!/usr/bin/env python3
"""Plot preregistered V2 severity sweep CSV (replicas vs wall p95)."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("docs/capability-extraction/v3/v2-severity-sweep-nx.csv"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/capability-extraction/v3/v2-severity-sweep-nx.png"),
    )
    args = parser.parse_args()

    series = defaultdict(list)
    with args.csv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            series[row["profile"]].append((int(row["replicas"]), float(row["wall_p95"])))

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; CSV is the reproducible artifact")
        return 1

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for profile, points in series.items():
        # mean p95 per replicas if repeats
        by_r = defaultdict(list)
        for r, p in points:
            by_r[r].append(p)
        xs = sorted(by_r)
        ys = [sum(by_r[x]) / len(by_r[x]) for x in xs]
        ax.plot(xs, ys, marker="o", label=profile)
        for x, ylist in by_r.items():
            for y in ylist:
                ax.scatter([x], [y], alpha=0.35)
    ax.axhline(190.0, color="black", linestyle="--", linewidth=1, label="Mission gate 190 ms")
    ax.set_xlabel("replicas (preregistered severity knob)")
    ax.set_ylabel("wall p95 (ms)")
    ax.set_title("V2 severity sweep — ENGINEERING ONLY")
    ax.legend()
    ax.grid(True, alpha=0.3)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=140)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
