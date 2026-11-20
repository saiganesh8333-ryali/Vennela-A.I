"""Errors specific to the Web Hunt Agent boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentFailure:
    code: str
    message: str
    retryable: bool = False


class WebHuntAgentError(Exception):
    """A structured failure raised for invalid agent configuration or input."""

    def __init__(self, failure: AgentFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)
