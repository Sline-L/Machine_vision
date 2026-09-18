#!/usr/bin/env python3
import json
from pathlib import Path

root = Path("/home/jetson/Projects/edgemedic-live/results/final_demo")
a = json.loads((root / "demo_a.json").read_text())["demo_a"]["recover"]
b = json.loads((root / "demo_b.json").read_text())["demo_b"]["recover"]
c = json.loads((root / "demo_c.json").read_text())["demo_c"]
print("DemoA", a["fault"], a["route"], round(a["e2e_ms"]), a["outcome"], "l2=", a["l2_invoked"])
print("DemoB", b["fault"], b["route"], round(b["e2e_ms"]), b["outcome"], "l2=", b["l2_invoked"])
on = c["memory_on"]["recover"]
off = c["memory_off"]["recover"]
print("DemoC_ON", on["route"], round(on["e2e_ms"]), "l2_invoked=", on["l2_invoked"], on["outcome"])
print(
    "DemoC_OFF",
    off["route"],
    round(off["e2e_ms"]),
    "l2_ms=",
    off["l2_ms"],
    "l2_invoked=",
    off["l2_invoked"],
    off["outcome"],
)
cited = {"A": 2153, "B": 2136, "C_on": 2241, "C_off": 4929, "l2": 2704}
print(
    "cite_match",
    {
        "A": abs(round(a["e2e_ms"]) - cited["A"]) <= 1,
        "B": abs(round(b["e2e_ms"]) - cited["B"]) <= 1,
        "C_on": abs(round(on["e2e_ms"]) - cited["C_on"]) <= 1,
        "C_off": abs(round(off["e2e_ms"]) - cited["C_off"]) <= 1,
        "l2": abs(round(off["l2_ms"]) - cited["l2"]) <= 1,
    },
)
