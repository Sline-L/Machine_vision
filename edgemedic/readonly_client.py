"""Strict read-only Control client for midterm observe-only demos.

Any attempt to POST /api/action raises. Dry-run strings are not a safety boundary.
"""


class ObserveOnlyViolation(RuntimeError):
    pass


class ReadOnlyControlClient:
    def __init__(self, base_url=None, timeout=2.0, snapshot=None):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._snapshot = snapshot

    def bind_snapshot(self, snapshot):
        self._snapshot = snapshot

    def get_state(self):
        if self._snapshot is not None:
            return self._snapshot
        if not self.base_url:
            raise ObserveOnlyViolation("no snapshot bound and no Control URL")
        import json
        from urllib.request import urlopen

        with urlopen(self.base_url + "/api/state", timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_action(self, *args, **kwargs):
        raise ObserveOnlyViolation(
            "observe-only client forbids post_action; midterm demo must not mutate GearPro"
        )

    def preview_action(self, *args, **kwargs):
        raise ObserveOnlyViolation(
            "observe-only client forbids preview_action (still POSTs /api/action)"
        )

    def _post_action(self, *args, **kwargs):
        raise ObserveOnlyViolation("observe-only client forbids _post_action")
