"""Process Manager tracking execution processes, threads, and PCB lifecycle transitions."""

from __future__ import annotations

import time
from typing import Any

from .agent import AgentPlatform, ExecutionResult
from .models import AgentAction
from .pcb import AutomationThread, ProcessControlBlock, ProcessState, TaskStatus


class ProcessManager:
    """Manages automation processes and handles PCB state transitions."""

    def __init__(self) -> None:
        self._processes: dict[str, ProcessControlBlock] = {}

    def create_process(
        self,
        goal: str,
        actions: list[AgentAction] | None = None,
        preferred_platform: AgentPlatform | None = None,
        context: dict[str, Any] | None = None,
    ) -> ProcessControlBlock:
        """Initialize a new PCB for an automation goal with required action threads."""
        pcb = ProcessControlBlock.create(
            goal=goal,
            actions=actions,
            preferred_platform=preferred_platform,
            context=context,
        )
        self._processes[pcb.process_id] = pcb
        return pcb

    def get_process(self, process_id: str) -> ProcessControlBlock | None:
        """Retrieve a PCB by process ID."""
        return self._processes.get(process_id)

    def list_processes(self, state: ProcessState | None = None) -> list[ProcessControlBlock]:
        """List active processes, optionally filtered by state."""
        processes = list(self._processes.values())
        if state is not None:
            processes = [p for p in processes if p.state == state]
        return processes

    def start_process(self, process_id: str) -> ProcessControlBlock:
        """Mark a process as actively running."""
        pcb = self._require_process(process_id)
        pcb.state = ProcessState.RUNNING
        pcb.updated_at = time.time()
        return pcb

    def update_thread(
        self,
        process_id: str,
        thread_id: str,
        status: TaskStatus,
        result: ExecutionResult | None = None,
        assigned_agent_id: str | None = None,
    ) -> AutomationThread:
        """Update state and result for a specific thread, recalculating parent PCB state."""
        pcb = self._require_process(process_id)
        thread = next((t for t in pcb.threads if t.thread_id == thread_id), None)
        if thread is None:
            raise KeyError(f"Thread '{thread_id}' not found in process '{process_id}'")

        thread.status = status
        thread.updated_at = time.time()
        if result is not None:
            thread.result = result
        if assigned_agent_id is not None:
            thread.assigned_agent_id = assigned_agent_id

        # Recalculate parent process state
        self._recalculate_process_state(pcb)
        return thread

    def cancel_process(self, process_id: str) -> ProcessControlBlock:
        """Cancel a process and all non-completed threads."""
        pcb = self._require_process(process_id)
        pcb.state = ProcessState.CANCELLED
        pcb.updated_at = time.time()
        for thread in pcb.threads:
            if thread.status in (TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.RUNNING):
                thread.status = TaskStatus.CANCELLED
                thread.updated_at = time.time()
        return pcb

    def _require_process(self, process_id: str) -> ProcessControlBlock:
        pcb = self._processes.get(process_id)
        if pcb is None:
            raise KeyError(f"Process '{process_id}' does not exist")
        return pcb

    def _recalculate_process_state(self, pcb: ProcessControlBlock) -> None:
        if not pcb.threads:
            return

        all_done = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for t in pcb.threads
        )
        any_failed = any(t.status == TaskStatus.FAILED for t in pcb.threads)
        any_running = any(t.status in (TaskStatus.RUNNING, TaskStatus.SCHEDULED) for t in pcb.threads)

        if all_done:
            if any_failed:
                pcb.state = ProcessState.FAILED
            else:
                pcb.state = ProcessState.COMPLETED
        elif any_running:
            pcb.state = ProcessState.RUNNING
        pcb.updated_at = time.time()
