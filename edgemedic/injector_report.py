"""Summarize injector sweep/qualify results for exploration review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _row(candidate, cycle, label):
    fault = cycle.get("fault") or {}
    healthy = cycle.get("healthy") or {}
    recovered = cycle.get("recovered") or {}
    sel = cycle.get("selectivity") or {}
    return {
        "label": label,
        "candidate": candidate,
        "pass": cycle.get("pass"),
        "triggerability": cycle.get("triggerability"),
        "margin": cycle.get("margin"),
        "sustainability": cycle.get("sustainability"),
        "reversible": cycle.get("reversible"),
        "healthy_v5_p95": healthy.get("v5_p95"),
        "fault_v5_p95": fault.get("v5_p95"),
        "recovered_v5_p95": recovered.get("v5_p95"),
        "hold_s": fault.get("overload_hold_s"),
        "locator_p95_fault": fault.get("locator_p95"),
        "valid_ratio_fault": fault.get("valid_ratio"),
        "gpu_clock_fault": fault.get("gpu_clock_mhz_p50"),
        "emc_mhz_fault": fault.get("emc_mhz_p50"),
        "power_w_fault": fault.get("power_w_p50"),
        "v5_delta_ms": sel.get("v5_delta_ms"),
        "locator_delta_ms": sel.get("locator_delta_ms"),
        "injector_config": cycle.get("injector_config") or candidate,
        "injector_hash": cycle.get("injector_hash"),
    }


def summarize_sweep(payload):
    rows = []
    for item in payload.get("candidates") or []:
        rows.append(_row(item.get("candidate"), item, "sweep"))
    return rows


def summarize_qualify(payload):
    rows = []
    spec = (payload.get("injector") or payload.get("provenance") or {}).get("fault_injector_config")
    for item in payload.get("cycles") or []:
        rows.append(_row(spec, item, f"repeat_{item.get('repeat')}"))
    return rows


def print_table(rows):
    headers = [
        "label",
        "kind",
        "pass",
        "hold_s",
        "healthy_v5",
        "fault_v5",
        "recovered_v5",
        "locator_fault",
        "emc",
        "gpu_clk",
    ]
    print("\t".join(headers))
    for row in rows:
        cand = row.get("candidate") or row.get("injector_config") or {}
        print(
            "\t".join(
                str(x)
                for x in [
                    row.get("label"),
                    cand.get("kind"),
                    row.get("pass"),
                    row.get("hold_s"),
                    row.get("healthy_v5_p95"),
                    row.get("fault_v5_p95"),
                    row.get("recovered_v5_p95"),
                    row.get("locator_p95_fault"),
                    row.get("emc_mhz_fault"),
                    row.get("gpu_clock_fault"),
                ]
            )
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize injector exploration results")
    parser.add_argument("summary", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    payload = _load(args.summary)
    stage = payload.get("stage") or ""
    if "qualify" in stage:
        rows = summarize_qualify(payload)
    else:
        rows = summarize_sweep(payload)
    print_table(rows)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"stage": stage, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    passed = [row for row in rows if row.get("pass")]
    print(f"\n{len(passed)}/{len(rows)} passed four gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
