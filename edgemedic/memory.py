"""Episode memory. A single verified success never becomes a Reflex rule."""

from collections import defaultdict
import json
from pathlib import Path

MIN_REPEATED_SUCCESS = 3

DEFAULT_PATH = Path(__file__).resolve().parent.parent / ".cache" / "edgemedic" / "episodes.json"


def _key(signature, name, params):
    blob = json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return f"{signature}|{name}|{blob}"


class EpisodeStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else DEFAULT_PATH
        self.successes = defaultdict(int)
        self.failures = defaultdict(int)
        self._load()

    def _load(self):
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for key, count in (data.get("successes") or {}).items():
            self.successes[key] = int(count)
        for key, count in (data.get("failures") or {}).items():
            self.failures[key] = int(count)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"successes": dict(self.successes), "failures": dict(self.failures)}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, signature, name, params, verified=False, verify_level=None):
        """Learn only function/mission recovery. Config-only must not enter the store."""
        if not signature or not name:
            return
        if verify_level == "config":
            return
        if verify_level == "none":
            verified = False
        elif verify_level in ("function", "mission"):
            verified = True
        key = _key(signature, name, params)
        if verified:
            self.successes[key] += 1
        else:
            self.failures[key] += 1
        self._save()

    def suggest(self, signature):
        """Return an action only after enough repeated verified successes."""
        if not signature:
            return None
        prefix = signature + "|"
        best = None
        best_score = 0
        for key, wins in self.successes.items():
            if not key.startswith(prefix):
                continue
            if wins < MIN_REPEATED_SUCCESS:
                continue
            fails = self.failures.get(key, 0)
            if wins <= fails:
                continue
            if wins > best_score:
                best_score = wins
                best = key
        if best is None:
            return None
        _sig, name, blob = best.split("|", 2)
        return {"name": name, "params": json.loads(blob)}
