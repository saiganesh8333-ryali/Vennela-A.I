from __future__ import annotations

from typing import Optional, Dict, Any, List
from .models import ProcessModel, ProcessType
from .pcb import PCB, ConcurrentUpdateError
from ..persistence.storage_adapter import SQLiteStorageAdapter, StorageError
from .states import validate_transition, ProcessState


class ProcessManager:
    """Authoritative manager for process lifecycle operations.

    Uses SQLiteStorageAdapter for persistence.
    """

    def __init__(self, storage: Optional[SQLiteStorageAdapter] = None):
        self.storage = storage or SQLiteStorageAdapter()

    def create_process(self, model: ProcessModel) -> None:
        if self.storage.exists(model.process_id):
            raise ValueError(f"Process already exists: {model.process_id}")
        self.storage.create(model.process_id, model.to_dict(), model.version)

    def get_process(self, process_id: str) -> Optional[ProcessModel]:
        obj = self.storage.get(process_id)
        if not obj:
            return None
        return ProcessModel.from_dict(obj)

    def update_process(self, model: ProcessModel, expected_version: int) -> None:
        # pass through optimistic concurrency
        try:
            self.storage.update(model.process_id, model.to_dict(), expected_version)
        except StorageError as e:
            raise ConcurrentUpdateError(str(e)) from e

    def transition_process(self, process_id: str, to_state: str, expected_version: int) -> None:
        pm = self.get_process(process_id)
        if not pm:
            raise ValueError(f"Process not found: {process_id}")
        pcb = PCB(pm)
        # version check
        pcb.bump_version_check(expected_version)
        # validate transition
        validate_transition(pm.state, to_state)
        pcb.transition(to_state)
        # persist
        self.update_process(pcb.model, expected_version)

    def cancel_process(self, process_id: str, expected_version: int) -> None:
        self.transition_process(process_id, ProcessState.CANCELLED.value, expected_version)

    def terminate_process(self, process_id: str, expected_version: int) -> None:
        self.transition_process(process_id, ProcessState.TERMINATED.value, expected_version)

    def complete_process(self, process_id: str, result: Dict[str, Any], expected_version: int) -> None:
        pm = self.get_process(process_id)
        if not pm:
            raise ValueError(f"Process not found: {process_id}")
        pcb = PCB(pm)
        pcb.bump_version_check(expected_version)
        validate_transition(pm.state, ProcessState.COMPLETED.value)
        pcb.model.result = result
        pcb.transition(ProcessState.COMPLETED.value)
        self.update_process(pcb.model, expected_version)

        # After completion, evaluate dependents: if all dependencies are satisfied,
        # transition dependents to QUEUED so scheduler can pick them up.
        dependents = self._find_dependents(process_id)
        for dep_id in dependents:
            dep_pm = self.get_process(dep_id)
            if not dep_pm:
                continue
            # Skip if already terminal or cancelled
            if dep_pm.state in (ProcessState.COMPLETED.value, ProcessState.FAILED.value, ProcessState.CANCELLED.value, ProcessState.TERMINATED.value):
                continue
            # If all dependencies completed, move to QUEUED
            if self._all_dependencies_completed(dep_pm):
                try:
                    # use current version as expected_version for safe update
                    self.transition_process(dep_pm.process_id, ProcessState.QUEUED.value, expected_version=dep_pm.version)
                except Exception:
                    # propagate? For now, avoid stopping the loop; log in future
                    pass

    def _all_dependencies_completed(self, pm: ProcessModel) -> bool:
        for d in pm.dependencies:
            dpm = self.get_process(d)
            if not dpm or dpm.state != ProcessState.COMPLETED.value:
                return False
        return True

    def _find_dependents(self, process_id: str) -> List[str]:
        # scan all processes to find those that list process_id as dependency
        ids: List[str] = []
        for obj in self.storage.list():
            pdata = obj
            deps = pdata.get("dependencies") or []
            if process_id in deps:
                ids.append(pdata.get("process_id"))
        return ids

    def fail_process(self, process_id: str, error: Dict[str, Any], expected_version: int) -> None:
        pm = self.get_process(process_id)
        if not pm:
            raise ValueError(f"Process not found: {process_id}")
        pcb = PCB(pm)
        pcb.bump_version_check(expected_version)
        pcb.model.error = error
        if pm.retry_policy and pm.retry_policy.attempts < pm.retry_policy.max_attempts:
            pcb.transition(ProcessState.RETRYING.value)
        else:
            pcb.transition(ProcessState.FAILED.value)
        self.update_process(pcb.model, expected_version)

        # After a failure, dependent processes must be blocked and record reason
        dependents = self._find_dependents(process_id)
        for dep_id in dependents:
            dep_pm = self.get_process(dep_id)
            if not dep_pm:
                continue
            if dep_pm.state in (ProcessState.COMPLETED.value, ProcessState.FAILED.value, ProcessState.CANCELLED.value, ProcessState.TERMINATED.value):
                continue
            try:
                self.set_blocked(dep_pm.process_id, reason=f"dependency_failed:{process_id}", expected_version=dep_pm.version)
            except Exception:
                # Do not stop on failure to block other dependents
                pass

    def set_blocked(self, process_id: str, reason: Optional[str], expected_version: int) -> None:
        pm = self.get_process(process_id)
        if not pm:
            raise ValueError(f"Process not found: {process_id}")
        pcb = PCB(pm)
        pcb.bump_version_check(expected_version)
        pcb.model.error = {"reason": reason} if reason else None
        pcb.transition(ProcessState.BLOCKED.value)
        self.update_process(pcb.model, expected_version)

    def list_processes(self) -> List[ProcessModel]:
        objs = self.storage.list()
        return [ProcessModel.from_dict(o) for o in objs]

    def list_by_state(self, state: str) -> List[ProcessModel]:
        allp = self.list_processes()
        return [p for p in allp if p.state == state]

    def add_child(self, parent_id: str, child_id: str) -> None:
        parent = self.get_process(parent_id)
        child = self.get_process(child_id)
        if not parent or not child:
            raise ValueError("Parent or child not found")
        if child_id in parent.child_ids:
            return
        parent.child_ids.append(child_id)
        self.update_process(parent, parent.version)

    def add_dependency(self, process_id: str, dependency_id: str) -> None:
        if process_id == dependency_id:
            raise ValueError("Self-dependency not allowed")
        pm = self.get_process(process_id)
        dep = self.get_process(dependency_id)
        if not pm or not dep:
            raise ValueError("Process or dependency not found")
        if dependency_id in pm.dependencies:
            return
        # prevent circular by simple DFS detection
        if self._detect_circular(process_id, dependency_id):
            raise ValueError("Circular dependency detected")
        pm.dependencies.append(dependency_id)
        self.update_process(pm, pm.version)

    def _detect_circular(self, start_id: str, new_dep_id: str) -> bool:
        # detect whether new_dep_id depends (directly or indirectly) on start_id
        stack = [new_dep_id]
        visited = set()
        while stack:
            cur = stack.pop()
            if cur == start_id:
                return True
            if cur in visited:
                continue
            visited.add(cur)
            cur_pm = self.get_process(cur)
            if cur_pm:
                for d in cur_pm.dependencies:
                    stack.append(d)
        return False

    def get_children(self, process_id: str) -> List[ProcessModel]:
        pm = self.get_process(process_id)
        if not pm:
            return []
        return [self.get_process(cid) for cid in pm.child_ids if self.get_process(cid) is not None]

    def get_parent(self, process_id: str) -> Optional[ProcessModel]:
        pm = self.get_process(process_id)
        if not pm:
            return None
        return self.get_process(pm.parent_id) if pm.parent_id else None

    def get_dependencies(self, process_id: str) -> List[ProcessModel]:
        pm = self.get_process(process_id)
        if not pm:
            return []
        return [self.get_process(d) for d in pm.dependencies if self.get_process(d) is not None]

    def can_run(self, process_id: str) -> bool:
        pm = self.get_process(process_id)
        if not pm:
            return False
        for dep in pm.dependencies:
            dpm = self.get_process(dep)
            if not dpm or dpm.state != ProcessState.COMPLETED.value:
                return False
        return True
