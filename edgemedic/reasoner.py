"""L2 reasoner: Qwen reads SystemSnapshot and may emit one whitelist action."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ALLOWED_TOOLS = (
    "restart_camera",
    "restart_worker",
    "reconnect_serial",
    "set_inference_profile",
    "set_locator_profile",
    "pause_inspection",
    "resume_inspection",
)

ALLOWED_PROFILES = ("FULL", "SPARSE", "SAFE_STOP", "TRT_FAST")
ALLOWED_LOCATORS = ("pt_safe", "trt_fast")

SYSTEM_PROMPT = """You are EdgeMedic L2 on GearPro. Output ONE JSON object only:
{"tool": "<name or null>", "params": {}}
Allowed tools: restart_camera, restart_worker, reconnect_serial, set_inference_profile, set_locator_profile, pause_inspection, resume_inspection.
set_inference_profile params.profile: FULL, SPARSE, SAFE_STOP, or TRT_FAST (TRT_FAST needs model1.engine).
set_locator_profile params.profile: pt_safe or trt_fast. That rebuilds inspector; never assign backend fields.
Never invent tools. Never shell, reboot, or edit files.
If healthy or unsure, {"tool": null, "params": {}}.
Do not repeat an action that just failed verify.
/no_think
"""


class ReasonerError(RuntimeError):
    pass


def _edit_distance(left, right):
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, char_l in enumerate(left, start=1):
        current = [i]
        for j, char_r in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (char_l != char_r)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def lexical_tool(name, allowed=ALLOWED_TOOLS):
    """Correct 1-2 character typos only when one whitelist name is uniquely closer."""
    if name in allowed:
        return name
    ranked = sorted((_edit_distance(name, item), item) for item in allowed)
    best_dist, best = ranked[0]
    if best_dist == 0:
        return best
    if best_dist > 2:
        return None
    if abs(len(name) - len(best)) > 2:
        return None
    if len(ranked) > 1 and ranked[1][0] <= best_dist:
        return None
    return best


def parse_tool_json(text):
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    if "<think>" in raw and "</think>" in raw:
        raw = raw.split("</think>", 1)[-1]
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
        tool = lexical_tool(str(tool))
        if tool is None:
            return None
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        params = {}
    if tool == "set_inference_profile":
        profile = params.get("profile")
        if profile not in ALLOWED_PROFILES:
            return None
    if tool == "set_locator_profile":
        profile = params.get("profile")
        if profile not in ALLOWED_LOCATORS:
            return None
    return {"name": tool, "params": params}


def _post_json(url, payload, timeout):
    raw = json.dumps(payload).encode("utf-8")
    request = Request(url, data=raw, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _message_text(data):
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = message.get("content") or message.get("reasoning_content") or choice.get("text") or ""
    if "<think>" in text and "</think>" in text:
        text = text.split("</think>", 1)[-1]
    return text


def complete(llm_url, snapshot, extra_note="", timeout=45.0):
    """Ask llama-server. Returns parsed action or None. Does not execute."""
    base = llm_url.rstrip("/")
    user = "SystemSnapshot:\n" + json.dumps(snapshot, ensure_ascii=False)
    if extra_note:
        user += "\n\nNote: " + extra_note
    chat_body = {
        "model": "qwen3-4b",
        "temperature": 0.0,
        "max_tokens": 160,
        "enable_thinking": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    try:
        data = _post_json(base + "/v1/chat/completions", chat_body, timeout)
        return parse_tool_json(_message_text(data))
    except HTTPError:
        pass
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ReasonerError(str(exc)) from exc

    prompt_body = {
        "prompt": SYSTEM_PROMPT + "\n\n" + user + "\n\nJSON:",
        "temperature": 0.0,
        "n_predict": 96,
    }
    try:
        data = _post_json(base + "/completion", prompt_body, timeout)
        text = data.get("content") or data.get("completion") or ""
        return parse_tool_json(text)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ReasonerError(str(exc)) from exc
