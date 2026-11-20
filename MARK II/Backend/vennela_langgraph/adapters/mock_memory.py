class MockMemoryAgent:
    def __init__(self, available: bool = True, empty: bool = False):
        self.available, self.empty = available, empty

    def retrieve(self, request: str) -> list[str]:
        if not self.available:
            raise RuntimeError("memory unavailable")
        return [] if self.empty else ["The user prefers concise, source-grounded answers."]
