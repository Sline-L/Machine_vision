"""Policy candidates from episode memory. Never auto-deployed into L1."""

from collections import defaultdict
import json

from .memory import MIN_REPEATED_SUCCESS, EpisodeStore


def generate_candidates(store=None):
    store = store or EpisodeStore()
    grouped = defaultdict(list)
    for key, wins in store.successes.items():
        signature, name, blob = key.split("|", 2)
        fails = store.failures.get(key, 0)
        if wins < MIN_REPEATED_SUCCESS or wins <= fails:
            continue
        grouped[signature].append(
            {
                "condition": signature,
                "action": {"name": name, "params": json.loads(blob)},
                "support": int(wins),
                "function_success": f"{wins}/{wins + fails}",
                "mission_success": None,
                "median_mttr": None,
                "status": "candidate",
            }
        )
    candidates = []
    for signature, items in grouped.items():
        items.sort(key=lambda item: item["support"], reverse=True)
        candidates.append(items[0])
    return candidates
