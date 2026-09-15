"""ENGINEERING ONLY harness for LATENCY_DEGRADED_V2.

NOT MISSION APPROVED.
Does not produce A3 effectiveness evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gp.capability_v2 import validate_frozen_artifacts, capability_identity_from_runtime
from gp.config import AppConfig
from gp.profiles import ProfileError, apply_to_config, available_capabilities


BANNER = """
============================================================
ENGINEERING ONLY — NOT MISSION APPROVED
LATENCY_DEGRADED_V2 harness
Formal admission remains CLOSED until fresh holdout PASS
============================================================
"""


def run_config_smoke() -> dict:
    print(BANNER)
    identity = validate_frozen_artifacts()
    config = AppConfig()
    rows = {r["profile_id"]: r for r in available_capabilities()}
    v2 = rows["LATENCY_DEGRADED_V2"]
    assert v2["implemented"] is True
    assert v2["mission_approved"] is False
    assert v2["available"] is False

    # Production path must reject.
    production_rejected = False
    try:
        apply_to_config(AppConfig(), "LATENCY_DEGRADED_V2", engineering_mode=False)
    except ProfileError:
        production_rejected = True

    # Engineering path must accept and switch Scratch topology.
    plan = apply_to_config(config, "LATENCY_DEGRADED_V2", engineering_mode=True)
    scratch = capability_identity_from_runtime(config.model2_config, config.defect_threshold)
    rollback = apply_to_config(config, "FULL", engineering_mode=True)
    full_scratch = capability_identity_from_runtime(config.model2_config, config.defect_threshold)
    report = {
        "mode": "ENGINEERING ONLY",
        "mission_approved": False,
        "frozen_identity": identity,
        "production_rejected": production_rejected,
        "engineering_plan": plan,
        "v2_scratch_identity": scratch,
        "rollback_plan": rollback,
        "full_scratch_identity": full_scratch,
        "registry_row": v2,
        "pass": bool(
            production_rejected
            and scratch.get("matches_latency_degraded_v2")
            and full_scratch.get("matches_full_scratch_v5")
            and plan.get("rebuild_inspector")
        ),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["pass"]:
        raise SystemExit(2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="ENGINEERING ONLY LATENCY_DEGRADED_V2 harness")
    parser.add_argument("--config-smoke", action="store_true", default=True)
    args = parser.parse_args(argv)
    if args.config_smoke:
        run_config_smoke()


if __name__ == "__main__":
    main()
