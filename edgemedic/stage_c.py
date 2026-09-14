"""Stage C profile bring-up. Not a controlled comparison and not A3 evidence."""

from pathlib import Path
import argparse
import json
import time

from edgemedic.provenance import FAULT_NONE, live_action, sample_live

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"

# FULL+TRT is inference profile TRT_FAST (FULL-quality interval + engine).
# Do not follow trt_fast with set_inference_profile FULL: that restores PT.
COMBOS = {
    "full_pt": (("set_inference_profile", {"profile": "FULL"}), ("set_locator_profile", {"profile": "pt_safe"})),
    "full_trt": (("set_locator_profile", {"profile": "trt_fast"}),),
    "sparse_pt": (("set_locator_profile", {"profile": "pt_safe"}), ("set_inference_profile", {"profile": "SPARSE"})),
    "sparse_trt": (("set_locator_profile", {"profile": "trt_fast"}), ("set_inference_profile", {"profile": "SPARSE"})),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage C profile sampler")
    parser.add_argument("--combo", choices=tuple(COMBOS), required=True)
    parser.add_argument("--protocol", choices=("bringup", "controlled"), default="bringup")
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--replay-pack", type=Path, default=Path("tests/replay"))
    parser.add_argument("--sample-s", type=float, default=None)
    parser.add_argument("--warmup-s", type=float, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    sample_s = 60.0 if args.protocol == "controlled" else 45.0
    warmup_s = 15.0 if args.protocol == "controlled" else 8.0
    if args.sample_s is not None:
        sample_s = float(args.sample_s)
    if args.warmup_s is not None:
        warmup_s = float(args.warmup_s)
    actions = []
    for name, params in COMBOS[args.combo]:
        result = live_action(args.control_url, name, params)
        actions.append(result)
        time.sleep(max(0.0, warmup_s))
    exp_config = {
        "kind": "stage_c_controlled" if args.protocol == "controlled" else "stage_c_bringup",
        "combo": args.combo,
        "protocol": args.protocol,
        "sample_s": sample_s,
        "warmup_s": warmup_s,
        "replay_pack_dir": str(args.replay_pack),
        "comparison": args.protocol == "controlled",
        "fault_mode": FAULT_NONE,
    }
    live = sample_live(
        args.control_url,
        duration_s=sample_s,
        fault_mode=FAULT_NONE,
        experiment_config=exp_config,
        reasoner="mock",
    )
    out = args.out or (RESULTS_ROOT / f"{args.protocol}_{args.combo}")
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "stage-c-controlled" if args.protocol == "controlled" else "stage-c-bringup",
        "combo": args.combo,
        "protocol": args.protocol,
        "comparison": args.protocol == "controlled",
        "experimentally_validated": False,
        "a3_claim": False,
        "actions": actions,
        "live": live,
        "summary": live.get("summary"),
        "provenance": live.get("provenance"),
    }
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"combo": args.combo, "protocol": args.protocol, "out": str(out), "verify": [item.get("verify_level") for item in actions], "summary": live.get("summary")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
