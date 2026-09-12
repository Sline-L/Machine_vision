"""Poll SystemSnapshot at 2 Hz: L0 → L1 → episode memory → L2 (Qwen)."""

import argparse
import time
import uuid

from .client import ControlClient
from .memory import EpisodeStore
from .policy import Memory, classify_fault, decide
from .reasoner import ReasonerError, complete


L2_COOLDOWN_S = 30.0
MEM_COOLDOWN_S = 10.0


def _execute(client, action, source):
    return client.post_action(
        action["name"],
        params=action.get("params") or {},
        source=source,
        request_id=action.get("request_id") or f"{source}-{uuid.uuid4().hex[:8]}",
    )


def _log(layer, rule, action, result):
    print(
        f"EdgeMedic {layer}/{rule}: {action['name']} {action.get('params')} "
        f"accepted={result.get('accepted')} verified={result.get('verified')} error={result.get('error')}"
    )


def run_loop(client, interval=0.5, once=False, llm_url=None, store=None):
    loop = Memory()
    store = store or EpisodeStore()
    last_l2 = 0.0
    last_mem = 0.0
    while True:
        try:
            snapshot = client.get_state()
        except Exception as exc:
            print(f"EdgeMedic: 无法读取 /api/state：{exc}")
            if once:
                return 1
            time.sleep(interval)
            continue

        fault = classify_fault(snapshot, loop)
        action = decide(snapshot, loop)
        executed = None
        result = None
        layer = None

        if action is not None:
            layer = action.get("layer") or "L1"
            result = _execute(client, action, "reflex")
            _log(layer, action.get("rule"), action, result)
            executed = action
            if not result.get("verified") and action.get("rule") == "WORKER_FAIL":
                loop.last_error_count = int(((snapshot.get("scratch_v5") or {}).get("error_count") or 0))

        l1_failed = executed is not None and not result.get("verified")
        if executed is None and fault and (time.monotonic() - last_mem) >= MEM_COOLDOWN_S:
            suggested = store.suggest(fault)
            if suggested is not None:
                suggested["request_id"] = f"MEM-{fault}-{uuid.uuid4().hex[:8]}"
                result = _execute(client, suggested, "reflex")
                _log("MEM", fault, suggested, result)
                executed = suggested
                layer = "MEM"
                last_mem = time.monotonic()
                l1_failed = not result.get("verified")

        need_l2 = llm_url and fault and (executed is None or l1_failed)
        if need_l2 and (time.monotonic() - last_l2) >= L2_COOLDOWN_S:
            note = ""
            if l1_failed:
                note = f"Previous action {executed['name']} failed verify: {result.get('error')}"
            try:
                proposed = complete(llm_url, snapshot, extra_note=note)
            except ReasonerError as exc:
                print(f"EdgeMedic L2 unavailable: {exc}")
                proposed = None
            last_l2 = time.monotonic()
            if proposed is not None:
                proposed["request_id"] = f"L2-{uuid.uuid4().hex[:8]}"
                result = _execute(client, proposed, "reasoner")
                _log("L2", fault or "UNKNOWN", proposed, result)
                executed = proposed
                layer = "L2"

        if executed is not None and fault:
            store.record(fault, executed["name"], executed.get("params") or {}, bool(result.get("verified")))

        if once:
            return 0
        time.sleep(interval)


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic L0/L1/memory/L2")
    parser.add_argument("--url", default="http://127.0.0.1:8787", help="GearPro Control API")
    parser.add_argument("--interval", type=float, default=0.5, help="snapshot poll period seconds")
    parser.add_argument("--once", action="store_true", help="one tick then exit")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080", help="llama-server base URL")
    parser.add_argument("--no-llm", action="store_true", help="never call Qwen")
    args = parser.parse_args(argv)
    llm_url = None if args.no_llm else args.llm_url
    extra = "no LLM" if llm_url is None else f"L2 {llm_url}"
    print(f"EdgeMedic watching {args.url} ({extra})")
    return run_loop(ControlClient(args.url), interval=args.interval, once=args.once, llm_url=llm_url)
