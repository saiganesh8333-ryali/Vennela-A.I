from time import perf_counter
from vennela_langgraph.core.contracts import StateUpdate
from vennela_langgraph.core.errors import BrainFailure, FailureCategory


class BaseNode:
    name = "node"

    def __init__(self, telemetry):
        self.telemetry = telemetry

    def failure(self, state, category: FailureCategory, message: str, recoverable: bool = False):
        return BrainFailure(category=category, message=message, node=self.name,
                            request_id=state.request_id, recoverable=recoverable,
                            attempt=state.attempts.get(self.name, 1))

    def run(self, state):
        started = perf_counter()
        attempt = state.attempts.get(self.name, 1)
        self.telemetry.record(state, self.name, "start", "running", started, attempt=attempt)
        try:
            update = self.execute(state)
            if update.failures:
                self.telemetry.record(
                    state, self.name, "failure", "failed", started,
                    update.failures[-1].category.value, attempt=attempt,
                )
            else:
                self.telemetry.record(state, self.name, "success", "success", started, attempt=attempt)
            return update
        except Exception as exc:
            self.telemetry.record(state, self.name, "failed", "failed", started, "UNKNOWN", attempt=attempt)
            raise

    def execute(self, state):
        raise NotImplementedError
