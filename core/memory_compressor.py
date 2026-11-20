def compress_memory(text: str):

    text = text.strip()

    replacements = {
        "i love": "Interested in",
        "i like": "Interested in",
        "my goal is": "Goal:"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text[:120]