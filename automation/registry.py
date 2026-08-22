from dataclasses import dataclass
from typing import Callable, Dict, Optional, Any
import threading


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]]
    func: Callable


class ToolRegistry:
    """Simple singleton registry for Level 1 tools."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ToolRegistry, cls).__new__(cls)
                cls._instance._tools = {}
            return cls._instance

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self):
        return list(self._tools.keys())
