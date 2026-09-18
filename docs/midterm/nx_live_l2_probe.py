#!/usr/bin/env python3
"""NX live L2 probe — reasoner.complete only, never Control post_action."""
import json
import sys
import time

sys.path.insert(0, "/home/jetson/Projects/edgemedic-live")
from edgemedic.reasoner import complete

snap = {
    "schema_version": "system-snapshot.v1",
    "system": {"temperature_c": 66.0},
    "camera": {
        "opened": True,
        "frame_seq": 900,
        "frame_age_ms": 1824,
        "read_failures": 2,
        "health": 0.0,
    },
    "locator": {"backend": "pt", "loaded": True, "latency_ms": 20.0, "health": 0.8},
    "scratch_v5": {"total_latency_ms": 60.0, "error_count": 0, "health": 0.7},
    "serial": {"connected": True, "consecutive_failures": 0, "health": 1.0},
    "mission": {
        "inspection_active": True,
        "output_valid": False,
        "current_profile": "FULL",
        "utility": 0.4,
    },
}

t0 = time.perf_counter()
out = complete("http://127.0.0.1:8080", snap)
ms = (time.perf_counter() - t0) * 1000
print(
    json.dumps(
        {
            "status": "LIVE INFERENCE",
            "l2_ms": round(ms, 1),
            "proposal": out,
            "note": "reasoner.complete only; no Control post_action",
        },
        ensure_ascii=False,
        indent=2,
    )
)
