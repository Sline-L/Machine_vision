"""python -m edgemedic — P0 Agent entry (observe-only by default)."""

from __future__ import annotations

import argparse
import json
import sys

from .runtime import EXECUTE_OBSERVE, EXECUTE_REPLAY, LoopState, make_client, run_once


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic P0 dual-specialist Agent")
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument(
        "--execution-mode",
        choices=(EXECUTE_OBSERVE, EXECUTE_REPLAY),
        default=EXECUTE_OBSERVE,
        help="observe_only never mutates; execute_replay POSTs low-risk actions",
    )
    parser.add_argument("--disable-l1", action="store_true", help="force L2 path for 4B evidence")
    parser.add_argument("--disable-memory", action="store_true")
    parser.add_argument("--force-l2", action="store_true")
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)

    if args.execution_mode == EXECUTE_REPLAY:
        print("WARNING: execute_replay enabled — Control POST allowed for whitelist actions", file=sys.stderr)

    client = make_client(args.url, args.execution_mode)
    llm = None if args.no_llm else args.llm_url
    cycle = run_once(
        client,
        LoopState(),
        llm_url=llm,
        execution_mode=args.execution_mode,
        disable_l1=args.disable_l1,
        disable_memory=args.disable_memory,
        force_l2=args.force_l2,
    )
    text = json.dumps(cycle, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
