"""Deterministic Automation Scheduler coordinating thread dispatch and resource validation."""

from __future__ import annotations

import time
from typing import Any

from .agent import ExecutionResult
from .gateway import AgentGateway
from .pcb import AutomationThread, ProcessControlBlock, ProcessState, TaskStatus
from .process import ProcessManager


class AutomationScheduler:
    """Schedules and executes automation threads via Agent Gateway with state tracking."""

    def __init__(
        self,
        gateway: AgentGateway,
        process_manager: ProcessManager | None = None,
    ) -> None:
        self.gateway = gateway
        self.process_manager = process_manager or ProcessManager()

    def run_process(self, pcb: ProcessControlBlock) -> ProcessControlBlock:
        """Schedule and execute all threads of a process sequentially."""
        self.process_manager.start_process(pcb.process_id)

        for thread in pcb.threads:
            if thread.status != TaskStatus.PENDING:
                continue

            self._execute_thread(pcb.process_id, thread)

            # If a thread fails, we halt sequential execution and mark remaining threads as cancelled
            if thread.status == TaskStatus.FAILED:
                for remaining in pcb.threads:
                    if remaining.status == TaskStatus.PENDING:
                        self.process_manager.update_thread(
                            pcb.process_id,
                            remaining.thread_id,
                            status=TaskStatus.CANCELLED,
                        )
                break

        return self.process_manager.get_process(pcb.process_id) or pcb

    def _execute_thread(self, process_id: str, thread: AutomationThread) -> AutomationThread:
        # Mark scheduled
        self.process_manager.update_thread(
            process_id,
            thread.thread_id,
            status=TaskStatus.SCHEDULED,
        )

        # Mark running
        self.process_manager.update_thread(
            process_id,
            thread.thread_id,
            status=TaskStatus.RUNNING,
        )

        # Dispatch via AgentGateway
        result, verification = self.gateway.dispatch(
            thread.action,
            preferred_platform=thread.target_platform,
            task_id=thread.thread_id,
        )

        # Determine final status
        if result.success and verification.verified:
            final_status = TaskStatus.COMPLETED
        else:
            final_status = TaskStatus.FAILED

        return self.process_manager.update_thread(
            process_id,
            thread.thread_id,
            status=final_status,
            result=result,
            assigned_agent_id=result.agent_id,
        )
