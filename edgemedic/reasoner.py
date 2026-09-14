"""L2 reasoner: Qwen reads SystemSnapshot and may emit one whitelist action."""

import json
import re
import time
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
    """Whitelist action from a *final* structured object. Ignores prompt-echo JSON in CoT."""
    report = classify_proposal(text)
    if report.get("invalid") or report.get("unsafe") or report.get("abstain"):
        return None
    return report.get("action")


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


UNSAFE_TOOLS = {"shell", "reboot", "run_shell", "bash", "exec", "powershell"}

PROTOCOL_VALID = "valid_structured"
INVALID_CLASSES = (
    "empty_output",
    "truncated_reasoning",
    "prose_refusal",
    "prompt_echo",
    "invalid_json",
    "schema_mismatch",
    "unknown_tool",
    "invalid_params",
    "think_leak",
    "truncated_output",
)

REFUSAL_MARKERS = (
    "cannot",
    "can't",
    "not enough",
    "insufficient",
    "i cannot",
    "as an ai",
    "sorry",
    "无法",
    "不能",
    "信息不足",
)

_INSTRUCTIONAL = re.compile(
    r"(if healthy or unsure|output one json|output \{|for example|such as|allowed tools|"
    r"never invent|do not repeat|you are edgemedic)",
    re.I,
)
_ANALYSIS = re.compile(
    r"(let'?s analyze|we are given|steps:|systemsnapshot|scratch_v5|frame_seq|locator:)",
    re.I,
)
_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.I | re.S)


def _strip_think(text):
    raw = "" if text is None else str(text)
    if "<think>" in raw and "</think>" in raw:
        return raw.split("</think>", 1)[-1].strip()
    return raw.strip()


def _looks_refusal(text):
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def _is_prompt_example(payload):
    if not isinstance(payload, dict):
        return False
    keys = set(payload)
    if not keys <= {"tool", "name", "params"}:
        return False
    if "tool" not in payload and "name" not in payload:
        return False
    tool = payload.get("tool") if "tool" in payload else payload.get("name")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return tool in (None, "", "null", "none", "None") and params == {}


def _iter_objects(text):
    decoder = json.JSONDecoder()
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            return
        try:
            payload, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        yield start, end, payload
        index = end


def _unclosed_object(text):
    start = text.rfind("{")
    if start < 0:
        return False
    try:
        json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError:
        return True
    return False


def extract_final_json(text):
    """Pick a final JSON object. Instruction-echo spans are not final answers."""
    body = _strip_think(text)
    if not body:
        return None, "empty_output"
    if "<think>" in (text or "") and "</think>" not in (text or ""):
        return None, "truncated_reasoning"
    fenced = _FENCE.findall(body)
    if fenced:
        try:
            payload = json.loads(fenced[-1])
            if isinstance(payload, dict):
                return payload, PROTOCOL_VALID
        except json.JSONDecodeError:
            return None, "invalid_json"
    try:
        whole = json.loads(body)
        if isinstance(whole, dict):
            return whole, PROTOCOL_VALID
    except json.JSONDecodeError:
        pass
    objects = list(_iter_objects(body))
    final = None
    echo_only = False
    for start, end, payload in objects:
        if not isinstance(payload, dict):
            continue
        instructional = bool(_INSTRUCTIONAL.search(body[max(0, start - 160) : start]))
        if instructional and _is_prompt_example(payload):
            echo_only = True
            continue
        if instructional:
            echo_only = True
            continue
        trailing = body[end:].strip()
        if trailing and not trailing.startswith("```"):
            if _ANALYSIS.search(trailing) or _INSTRUCTIONAL.search(trailing):
                continue
        final = payload
    if final is not None:
        return final, PROTOCOL_VALID
    if echo_only:
        return None, "prompt_echo"
    if _looks_refusal(body) and not objects:
        return None, "prose_refusal"
    if _unclosed_object(body) or _ANALYSIS.search(body):
        return None, "truncated_reasoning"
    if _looks_refusal(body):
        return None, "prose_refusal"
    if "{" in body:
        return None, "invalid_json"
    return None, "invalid_json"


def classify_invalid_kind(text, report=None):
    """Protocol-failure label. Does not score tool choice."""
    del report
    _, kind = extract_final_json(text)
    if kind == PROTOCOL_VALID:
        return None
    return kind or "invalid_json"


def _score_payload(payload, report):
    if not isinstance(payload, dict):
        report["invalid"] = True
        report["invalid_class"] = "schema_mismatch"
        report["protocol_status"] = "schema_mismatch"
        return report
    if "tool" not in payload and "name" not in payload:
        report["invalid"] = True
        report["invalid_class"] = "schema_mismatch"
        report["protocol_status"] = "schema_mismatch"
        return report
    tool = payload.get("tool") if "tool" in payload else payload.get("name")
    report["raw_tool"] = tool
    if tool in (None, "", "null", "none", "None"):
        report["abstain"] = True
        report["protocol_status"] = PROTOCOL_VALID
        return report
    tool = str(tool)
    lowered = tool.lower()
    if lowered in UNSAFE_TOOLS or "shell" in lowered or "reboot" in lowered:
        report["unsafe"] = True
        report["protocol_status"] = PROTOCOL_VALID
        return report
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    name = tool if tool in ALLOWED_TOOLS else lexical_tool(tool)
    if name is None:
        report["invalid"] = True
        report["invalid_class"] = "unknown_tool"
        report["protocol_status"] = "unknown_tool"
        return report
    action = {"name": name, "params": params}
    if name == "set_inference_profile" and params.get("profile") not in ALLOWED_PROFILES:
        report["invalid"] = True
        report["invalid_class"] = "invalid_params"
        report["protocol_status"] = "invalid_params"
        return report
    if name == "set_locator_profile" and params.get("profile") not in ALLOWED_LOCATORS:
        report["invalid"] = True
        report["invalid_class"] = "invalid_params"
        report["protocol_status"] = "invalid_params"
        return report
    report["parsed"] = action
    report["action"] = action
    report["protocol_status"] = PROTOCOL_VALID
    return report


def classify_proposal(text):
    """Final-answer extract → schema check. CoT JSON echo is not a decision."""
    report = {
        "action": None,
        "raw_tool": None,
        "abstain": False,
        "invalid": False,
        "unsafe": False,
        "parsed": None,
        "invalid_class": None,
        "protocol_status": None,
    }
    payload, kind = extract_final_json(text)
    if kind != PROTOCOL_VALID:
        report["invalid"] = True
        report["invalid_class"] = kind or "invalid_json"
        report["protocol_status"] = report["invalid_class"]
        return report
    return _score_payload(payload, report)


def complete_report(llm_url, snapshot, extra_note="", timeout=45.0):
    """Ask llama-server. Returns metrics plus a parsed action. Does not execute."""
    started = time.monotonic()
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
    raw_text = ""
    tokens = None
    try:
        data = _post_json(base + "/v1/chat/completions", chat_body, timeout)
        raw_text = _message_text(data)
        usage = data.get("usage") or {}
        tokens = usage.get("total_tokens")
    except HTTPError:
        raw_text = ""
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ReasonerError(str(exc)) from exc

    if not raw_text:
        prompt_body = {
            "prompt": SYSTEM_PROMPT + "\n\n" + user + "\n\nJSON:",
            "temperature": 0.0,
            "n_predict": 96,
        }
        try:
            data = _post_json(base + "/completion", prompt_body, timeout)
            raw_text = data.get("content") or data.get("completion") or ""
            tokens = data.get("tokens_predicted") or tokens
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise ReasonerError(str(exc)) from exc

    proposal = classify_proposal(raw_text)
    proposal["latency_s"] = round(time.monotonic() - started, 3)
    proposal["tokens"] = tokens
    proposal["raw"] = raw_text
    return proposal


def complete(llm_url, snapshot, extra_note="", timeout=45.0):
    """Ask llama-server. Returns parsed action or None. Does not execute."""
    return complete_report(llm_url, snapshot, extra_note=extra_note, timeout=timeout).get("action")
