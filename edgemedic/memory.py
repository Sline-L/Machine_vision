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
        self.suggests = 0
        self.harms = 0
        self.misguided = 0
        self.executed = 0
        self.executed_harms = 0
        self.harmful = 0
        self.caught = 0
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
        self.suggests = int(data.get("suggests") or 0)
        self.harms = int(data.get("harms") or 0)
        self.misguided = int(data.get("misguided") or 0)
        self.executed = int(data.get("executed") or 0)
        self.executed_harms = int(data.get("executed_harms") or 0)
        self.harmful = int(data.get("harmful") or 0)
        self.caught = int(data.get("caught") or 0)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "successes": dict(self.successes),
            "failures": dict(self.failures),
            "suggests": int(self.suggests),
            "harms": int(self.harms),
            "misguided": int(self.misguided),
            "executed": int(self.executed),
            "executed_harms": int(self.executed_harms),
            "harmful": int(self.harmful),
            "caught": int(self.caught),
        }
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

    def harm_rate(self):
        """Deprecated alias of executed-harm rate when only live stickiness is tracked."""
        if self.executed <= 0:
            if self.suggests <= 0:
                return 0.0
            return self.harms / self.suggests
        return self.executed_harms / self.executed

    def misguidance_rate(self):
        if self.suggests <= 0:
            return 0.0
        return self.misguided / self.suggests

    def catch_rate(self):
        if self.harmful <= 0:
            return None
        return self.caught / self.harmful

    def mark_suggestion(self, accepted=True, verify_level="none"):
        """Live path: blocked vs executed harm."""
        self.suggests += 1
        blocked = not accepted
        if blocked:
            self.harmful += 1
            self.caught += 1
            self.misguided += 1
        else:
            self.executed += 1
            if verify_level == "none":
                self.executed_harms += 1
                self.harms += 1
                self.harmful += 1
                self.misguided += 1
        self._save()

    def evaluate_suggestion(self, suggested, acceptable_actions=None, abstain_allowed=True, blocked=False):
        from .metrics import classify_memory_proposal

        outcome = classify_memory_proposal(suggested, acceptable_actions, abstain_allowed, blocked=blocked)
        self.suggests += 1
        if outcome["incorrect"]:
            self.misguided += 1
        if outcome["harmful"]:
            self.harmful += 1
        if outcome["caught"]:
            self.caught += 1
        if outcome["executed"]:
            self.executed += 1
        if outcome["harm"]:
            self.executed_harms += 1
            self.harms += 1
        self._save()
        return outcome["harm"] if not blocked else outcome["incorrect"]


def _action_matches(action, spec):
    if spec is None:
        return action is None
    if action is None:
        return False
    name = action.get("name")
    if spec.get("tool") and name != spec.get("tool"):
        return False
    if spec.get("name") and name != spec.get("name"):
        return False
    params = spec.get("params")
    if params:
        actual = action.get("params") or {}
        for key, value in params.items():
            if actual.get(key) != value:
                return False
    return True
