def classify_memory(text: str):
    if not isinstance(text, str) or not text.strip():
        return "general"

    text_lower = text.lower()

    if "my name is" in text_lower or "call me" in text_lower:
        return "profile"

    if any(marker in text_lower for marker in ("i want", "my goal", "goal is", "dream", "aspiration")):
        return "goal"

    if (
        "i like" in text_lower
        or "i love" in text_lower
        or "favorite" in text_lower
        or "prefer" in text_lower
        or "i enjoy" in text_lower
    ):
        return "preference"

    if any(marker in text_lower for marker in ("project", "working on", "building")):
        return "project"

    if any(marker in text_lower for marker in ("i can ", "i know ", "my skill", "experienced in")):
        return "skill"

    if any(marker in text_lower for marker in ("my ", "is ", " are ", " lives in", " work at")):
        return "fact"

    if any(marker in text_lower for marker in ("error", "problem", "failed", "finished", "completed")):
        return "event"

    return "general"