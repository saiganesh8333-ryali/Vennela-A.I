class MockLLM:
    provider = "mock"
    model = "deterministic-v1"

    def generate(self, request: str, context: list[str], evidence: list[object], reasoning_level: str) -> str:
        if evidence:
            facts = "; ".join(e.extracted_facts[0] for e in evidence if e.extracted_facts)
            return f"Based on the available sources: {facts}"
        if context:
            return f"I found this relevant context: {context[0]}"
        return f"Understood: {request}"
