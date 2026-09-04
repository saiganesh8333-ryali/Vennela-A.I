import re

def classify_memory(text: str):
    if not isinstance(text, str) or not text.strip():
        return "general"

    text_lower = text.lower()

    if "i want" in text_lower or "goal" in text_lower:
        return "goal"

    if (
        "i like" in text_lower
        or "i love" in text_lower
        or "favorite" in text_lower
        or "prefer" in text_lower
    ):
        return "preference"

    if "error" in text_lower or "problem" in text_lower:
        return "event"

    return "general"