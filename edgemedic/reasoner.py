"""L2 reasoner: Qwen reads SystemSnapshot and may emit one whitelist action."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ALLOWED_TOOLS = (
    "restart_camera",
    "restart_worker",
    "reconnect_serial",
    "set_inference_profile",
    "pause_inspection",
    "resume_inspection",
)

ALLOWED_PROFILES = ("FULL", "SPARSE", "SAFE_STOP")

SYSTEM_PROMPT = """You are EdgeMedic L2 on GearPro. Output ONE JSON object only:
{"tool": "<name or null>", "params": {}}
Allowed tools: restart_camera, restart_worker, reconnect_serial, set_inference_profile, pause_inspection, resume_inspection.
set_inference_profile params.profile must be FULL, SPARSE, or SAFE_STOP.
Never invent tools. Never shell, reboot, or edit files.
If the snapshot is healthy or you are unsure, output {"tool": null, "params": {}}.
Do not repeat an action that just failed verify.
"""


class ReasonerError(RuntimeError):
    pass


def parse_tool_json(text):
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    tool = payload.get("tool") or payload.get("name")
    if not tool or tool in ("null", "none", "None"):
        return None
    if tool not in ALLOWED_TOOLS:
        return None
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        params = {}
    if tool == "set_inference_profile":
        profile = params.get("profile")
        if profile not in ALLOWED_PROFILES:
            return None
    return {"name": tool, "params": params}


def _post_json(url, payload, timeout):
    raw = json.dumps(payload).encode("utf-8")
    request = Request(url, data=raw, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def complete(llm_url, snapshot, extra_note="", timeout=20.0):
    """Ask llama-server. Returns parsed action or None. Does not execute."""
    base = llm_url.rstrip("/")
    user = "SystemSnapshot:\n" + json.dumps(snapshot, ensure_ascii=False)
    if extra_note:
        user += "\n\nNote: " + extra_note
    chat_body = {
        "model": "qwen3-4b",
        "temperature": 0.1,
        "max_tokens": 256,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    try:
        data = _post_json(base + "/v1/chat/completions", chat_body, timeout)
        text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        return parse_tool_json(text)
    except HTTPError:
        pass
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ReasonerError(str(exc)) from exc

    prompt_body = {
        "prompt": SYSTEM_PROMPT + "\n\n" + user + "\n\nJSON:",
        "temperature": 0.1,
        "n_predict": 256,
    }
    try:
        data = _post_json(base + "/completion", prompt_body, timeout)
        text = data.get("content") or data.get("completion") or ""
        return parse_tool_json(text)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ReasonerError(str(exc)) from exc
