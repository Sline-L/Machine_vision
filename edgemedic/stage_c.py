"""Stage C profile bring-up. Not a controlled comparison and not A3 evidence."""

from pathlib import Path
import argparse
import json
import time

from edgemedic.provenance import FAULT_NONE, live_action, sample_live

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"

COMBOS = {
    "full_pt": (("set_inference_profile", {"profile": "FULL"}), ("set_locator_profile", {"profile": "pt_safe"})),
    "full_trt": (("set_locator_profile", {"profile": "trt_fast"}), ("set_inference_profile", {"profile": "FULL"})),
    "sparse_pt": (("set_locator_profile", {"profile": "pt_safe"}), ("set_inference_profile", {"profile": "SPARSE"})),
    "sparse_trt": (("set_locator_profile", {"profile": "trt_fast"}), ("set_inference_profile", {"profile": "SPARSE"})),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage C bring-up sampler")
    parser.add_argument("--combo", choices=tuple(COMBOS), required=True)
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--replay-pack", type=Path, default=Path("tests/replay"))
    parser.add_argument("--sample-s", type=float, default=45.0)
    parser.add_argument("--warmup-s", type=float, default=8.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    actions = []
    for name, params in COMBOS[args.combo]:
        result = live_action(args.control_url, name, params)
        actions.append(result)
        time.sleep(max(0.0, float(args.warmup_s)))
    exp_config = {
        "kind": "stage_c_bringup",
        "combo": args.combo,
        "sample_s": args.sample_s,
        "warmup_s": args.warmup_s,
        "replay_pack_dir": str(args.replay_pack),
        "comparison": False,
        "fault_mode": FAULT_NONE,
    }
    live = sample_live(
        args.control_url,
        duration_s=args.sample_s,
        fault_mode=FAULT_NONE,
        experiment_config=exp_config,
        reasoner="mock",
    )
    out = args.out or (RESULTS_ROOT / f"bringup_{args.combo}")
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "stage-c-bringup",
        "combo": args.combo,
        "comparison": False,
        "experimentally_validated": False,
        "actions": actions,
        "live": live,
        "summary": live.get("summary"),
        "provenance": live.get("provenance"),
    }
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"combo": args.combo, "out": str(out), "verify": [item.get("verify_level") for item in actions], "summary": live.get("summary")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
