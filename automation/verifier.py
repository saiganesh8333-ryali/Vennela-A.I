"""Execution Result Verification and Recovery Validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .agent import ExecutionResult
from .models import ActionType, AgentAction


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    INVALID_PAYLOAD = "invalid_payload"


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    verified: bool
    message: str
    details: dict[str, Any] | None = None


class ExecutionVerifier:
    """Validates execution results returned by device agents against action specifications."""

    def verify(self, action: AgentAction, result: ExecutionResult) -> VerificationResult:
        """Verify that the execution result satisfies the action contract."""
        if not result.success:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                verified=False,
                message=result.error or "Agent reported execution failure",
                details={"action_type": action.type.value, "task_id": result.task_id},
            )

        # Validate that output exists and is a dictionary
        if not isinstance(result.output, dict):
            return VerificationResult(
                status=VerificationStatus.INVALID_PAYLOAD,
                verified=False,
                message="Execution result output must be a key-value dictionary",
                details={"action_type": action.type.value, "task_id": result.task_id},
            )

        # Action-specific verification checks
        if action.type is ActionType.OPEN_APP:
            if action.target and "target" in result.output:
                if str(result.output["target"]).lower() != action.target.lower():
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        verified=False,
                        message=f"Opened app mismatch: expected '{action.target}', got '{result.output.get('target')}'",
                        details={"expected": action.target, "actual": result.output.get("target")},
                    )

        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            verified=True,
            message="Execution verified successfully",
            details=result.output,
        )
