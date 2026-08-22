import json
import re
from typing import Optional, Dict, Any
from lightweight_nlp import classify_intent


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    # Try parsing entire text first
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "tool" in obj:
            return obj
    except Exception:
        pass

    # Fallback: find first JSON object-looking substring using a simple brace-matching scanner
    start = None
    depth = 0
    for i, ch in enumerate(text):
        if ch == '{':
            if start is None:
                start = i
            depth += 1
        elif ch == '}' and start is not None:
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and "tool" in obj:
                        return obj
                except Exception:
                    # continue searching after this position
                    start = None
                    depth = 0
                    continue
    return None


def map_llm_response_to_action(llm_text: str) -> Optional[Dict[str, Any]]:
    """Map LLM response to a tool action dict: { 'tool': str, 'arguments': {...} }

    Strategy:
    - If LLM returned an explicit JSON object with 'tool', trust that and return it.
    - Otherwise, run a lightweight intent classifier to heuristically map common intents.
    """
    # Try explicit JSON first
    obj = _extract_json_object(llm_text)
    if obj:
        # Ensure arguments key
        if "arguments" not in obj:
            obj["arguments"] = {}
        return {"tool": obj.get("tool"), "arguments": obj.get("arguments", {})}

    # Heuristic fallback using lightweight intent classifier on the text
    intents = classify_intent(llm_text)
    # intents is a dict label->score
    # Pick the highest scoring intent label
    if intents:
        top_intent = max(intents.items(), key=lambda x: x[1])[0]
    else:
        top_intent = "statement"

    top_intent = top_intent.lower()

    # Map some common intents to tools
    if top_intent in ("question", "greeting", "statement"):
        return None
    if "time" in llm_text.lower() or top_intent == "question" and "time" in llm_text.lower():
        return {"tool": "get_time", "arguments": {}}
    if "system" in llm_text.lower() and "info" in llm_text.lower():
        return {"tool": "get_system_info", "arguments": {}}

    # URL patterns
    url_match = re.search(r"https?://[\w\-\./?=&%]+", llm_text)
    if url_match:
        return {"tool": "open_url", "arguments": {"url": url_match.group(0)}}

    # Defaults: no actionable tool found
    return None
