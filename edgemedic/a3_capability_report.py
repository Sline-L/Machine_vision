"""Print FULL vs SPARSE severity response table from a3_capability summary."""

from pathlib import Path
import argparse
import csv
import json


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    args = parser.parse_args(argv)
    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("points") or []:
        sev = item.get("severity") or {}
        steady = item.get("steady") or {}
        rows.append(
            {
                "severity": sev.get("id"),
                "label": sev.get("label"),
                "load_ms": sev.get("load_ms"),
                "idle_ms": sev.get("idle_ms"),
                "profile": item.get("profile"),
                "aborted": item.get("aborted"),
                "v5_p50": steady.get("v5_p50"),
                "v5_p95": steady.get("v5_p95"),
                "locator_p95": steady.get("locator_p95"),
                "cycle_rate_hz": steady.get("cycle_rate_hz"),
                "valid_ratio": steady.get("valid_ratio"),
                "utility_mean": steady.get("utility_mean"),
                "gpu_clk": steady.get("gpu_clock_mhz_p50"),
                "power_w": steady.get("power_w_p50"),
                "temp_c": steady.get("temperature_c_p50"),
            }
        )
    print(
        "sev\tprofile\tload/idle\tv5_p50\tv5_p95\tloc_p95\tcycle_hz\tvalid\tutility\tgpu_clk\tpower\ttemp"
    )
    for row in rows:
        print(
            "\t".join(
                str(x)
                for x in [
                    row["severity"],
                    row["profile"],
                    f"{row['load_ms']}/{row['idle_ms']}",
                    row["v5_p50"],
                    row["v5_p95"],
                    row["locator_p95"],
                    row["cycle_rate_hz"],
                    row["valid_ratio"],
                    row["utility_mean"],
                    row["gpu_clk"],
                    row["power_w"],
                    row["temp_c"],
                ]
            )
        )
    # Pairwise deltas
    by = {}
    for row in rows:
        if row.get("aborted"):
            continue
        by.setdefault(row["severity"], {})[row["profile"]] = row
    print("\nFULL - SPARSE deltas (positive => FULL higher):")
    print("sev\tdV5_p95\td_cycle_hz\td_utility\td_locator_p95")
    for sev in sorted(by):
        full = by[sev].get("FULL") or {}
        sparse = by[sev].get("SPARSE") or {}
        if not full or not sparse:
            continue

        def d(key):
            a, b = full.get(key), sparse.get(key)
            if a is None or b is None:
                return None
            return round(float(a) - float(b), 3)

        print(f"{sev}\t{d('v5_p95')}\t{d('cycle_rate_hz')}\t{d('utility_mean')}\t{d('locator_p95')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
