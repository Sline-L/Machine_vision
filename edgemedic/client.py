"""HTTP client for GearPro Control API. Does not import gp."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ControlClient:
    def __init__(self, base_url, timeout=2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_state(self):
        with urlopen(self.base_url + "/api/state", timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def preview_action(self, name, params=None, source="reasoner", request_id="q3-preview", snapshot=None):
        payload = {
            "name": name,
            "params": params or {},
            "source": source,
            "request_id": request_id,
            "dry_run": True,
        }
        if snapshot is not None:
            payload["snapshot"] = snapshot
        return self._post_action(payload, timeout=self.timeout)

    def post_action(self, name, params=None, source="reflex", request_id="reflex", timeout=None):
        payload = {
            "name": name,
            "params": params or {},
            "source": source,
            "request_id": request_id,
        }
        wait = timeout if timeout is not None else max(self.timeout, 8.0)
        return self._post_action(payload, timeout=wait)

    def _post_action(self, payload, timeout):
        raw = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + "/api/action",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        dry = bool(payload.get("dry_run"))
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"accepted": False, "executed": False, "dry_run": dry, "error": body}
        except URLError as exc:
            return {"accepted": False, "executed": False, "dry_run": dry, "error": str(exc.reason)}
