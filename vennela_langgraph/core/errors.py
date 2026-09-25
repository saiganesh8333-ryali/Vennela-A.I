from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class FailureCategory(str, Enum):
    VALIDATION = "VALIDATION"
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    PROVIDER = "PROVIDER"
    ROUTER = "ROUTER"
    AGENT = "AGENT"
    TOOL = "TOOL"
    VERIFICATION = "VERIFICATION"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"
    SCHEMA = "SCHEMA"
    CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
    DEPENDENCY = "DEPENDENCY"


class BrainFailure(BaseModel):
    category: FailureCategory
    message: str
    node: str
    request_id: str
    recoverable: bool = False
    attempt: int = 1
    failure_kind: Optional[FailureCategory] = None
    retryable: Optional[bool] = None
    detail: Optional[str] = None

    @model_validator(mode="after")
    def populate_compatibility_fields(self):
        if self.failure_kind is None:
            self.failure_kind = self.category
        if self.retryable is None:
            self.retryable = self.recoverable
        return self


class NodeExecutionError(Exception):
    def __init__(self, failure: BrainFailure):
        super().__init__(failure.message)
        self.failure = failure
