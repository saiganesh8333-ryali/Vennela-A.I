from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field
import time


@dataclass
class Resource:
    resource_id: str
    capacity: int = 1  # 1 -> mutex behavior, >1 -> semaphore
    holders: Dict[str, int] = field(default_factory=dict)  # process_id -> count
    waiters: deque = field(default_factory=deque)  # queue of (process_id, count, timestamp)


class ResourceManager:
    """Lightweight in-memory resource manager with mutex/semaphore semantics.

    - register_resource(resource_id, capacity)
    - request(resource_id, process_id, count=1) -> bool (granted or queued)
    - release(resource_id, process_id, count=1) -> bool
    - status(resource_id) -> dict
    - list_locked_resources() -> List[str]

    This implementation is non-blocking for requests: if not enough capacity,
    the request is queued. The caller can poll or listen for events in later
    phases when a scheduler/worker/notification system exists.
    """

    def __init__(self):
        self._resources: Dict[str, Resource] = {}

    def register_resource(self, resource_id: str, capacity: int = 1) -> None:
        if resource_id in self._resources:
            # update capacity if needed
            self._resources[resource_id].capacity = capacity
            return
        self._resources[resource_id] = Resource(resource_id=resource_id, capacity=capacity)

    def request(self, resource_id: str, process_id: str, count: int = 1) -> bool:
        if resource_id not in self._resources:
            # auto-register with capacity=1
            self.register_resource(resource_id, capacity=1)
        res = self._resources[resource_id]
        available = res.capacity - sum(res.holders.values())
        if available >= count:
            # grant
            res.holders[process_id] = res.holders.get(process_id, 0) + count
            return True
        else:
            # queue the request
            res.waiters.append((process_id, count, time.time()))
            return False

    def release(self, resource_id: str, process_id: str, count: int = 1) -> bool:
        if resource_id not in self._resources:
            return False
        res = self._resources[resource_id]
        held = res.holders.get(process_id, 0)
        if held < count:
            return False
        # release
        res.holders[process_id] = held - count
        if res.holders[process_id] == 0:
            del res.holders[process_id]
        # try to grant queued waiters in FIFO order
        self._grant_waiters(res)
        return True

    def _grant_waiters(self, res: Resource) -> None:
        # attempt to fulfill waiters in FIFO order
        while res.waiters:
            pid, cnt, _ts = res.waiters[0]
            available = res.capacity - sum(res.holders.values())
            if available >= cnt:
                # grant
                res.waiters.popleft()
                res.holders[pid] = res.holders.get(pid, 0) + cnt
            else:
                break

    def status(self, resource_id: str) -> Optional[Dict]:
        if resource_id not in self._resources:
            return None
        res = self._resources[resource_id]
        return {
            "resource_id": res.resource_id,
            "capacity": res.capacity,
            "holders": dict(res.holders),
            "waiters": list(res.waiters),
        }

    def list_locked_resources(self) -> List[str]:
        return [rid for rid, r in self._resources.items() if r.holders]

    def clear(self) -> None:
        self._resources.clear()
