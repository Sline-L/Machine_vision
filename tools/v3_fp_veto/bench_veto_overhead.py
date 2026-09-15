#!/usr/bin/env python3
"""Micro-benchmark V3-1 logistic/MLP veto overhead (ms)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np


def load_model(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    mean = np.asarray(payload["mean"], dtype=np.float64)
    std = np.asarray(payload["std"], dtype=np.float64)
    if payload["type"] == "logistic":
        w = np.asarray(payload["weights"], dtype=np.float64)
        b = float(payload["bias"])

        def predict(x):
            xs = (x - mean) / std
            z = float(xs @ w + b)
            z = min(max(z, -30), 30)
            return 1.0 / (1.0 + np.exp(-z))

        return predict, payload
    w1 = np.asarray(payload["w1"], dtype=np.float64)
    b1 = np.asarray(payload["b1"], dtype=np.float64)
    w2 = np.asarray(payload["w2"], dtype=np.float64)
    b2 = float(payload["b2"])

    def predict(x):
        xs = (x - mean) / std
        h = np.tanh(xs @ w1 + b1)
        z = float(h @ w2 + b2)
        z = min(max(z, -30), 30)
        return 1.0 / (1.0 + np.exp(-z))

    return predict, payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--iters", type=int, default=20000)
    args = parser.parse_args()

    import csv

    predict, payload = load_model(args.model)
    names = payload["feature_names"]
    with args.features.open(encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    x = np.asarray([float(row[n]) for n in names], dtype=np.float64)

    for _ in range(1000):
        predict(x)
    t0 = time.perf_counter()
    for _ in range(args.iters):
        predict(x)
    elapsed = time.perf_counter() - t0
    per_ms = (elapsed / args.iters) * 1000.0
    report = {
        "iters": args.iters,
        "per_call_ms": per_ms,
        "p95_budget_s1_ms": 12.0,
        "budget_ok": per_ms < 1.0,
        "model_type": payload["type"],
        "note": "CPU numpy veto only; excludes backbone. S1 envelope preserved if backbone==V2.",
    }
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
