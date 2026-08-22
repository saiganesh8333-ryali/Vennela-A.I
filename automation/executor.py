import time
from typing import Any, Dict
from .registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or ToolRegistry()

    def _validate_args(self, tool, args: Dict[str, Any]):
        schema = tool.input_schema or {}
        # schema expected as dict with optional 'required' list
        required = schema.get("required", []) if isinstance(schema, dict) else []
        missing = [r for r in required if r not in (args or {})]
        if missing:
            raise ValueError(f"Missing required arguments: {missing}")

    def execute(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        start = time.time()
        tool = self.registry.get(tool_name)
        if not tool:
            return {
                "success": False,
                "tool": tool_name,
                "error": {"type": "ToolNotFound", "message": "Tool is not registered."}
            }

        try:
            self._validate_args(tool, arguments or {})
        except Exception as e:
            return {
                "success": False,
                "tool": tool_name,
                "error": {"type": "InvalidArguments", "message": str(e)}
            }

        try:
            result = tool.func(arguments or {})
            duration = time.time() - start
            logger.info(f"Executed tool {tool_name} in {duration:.3f}s")
            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "metadata": {"duration_seconds": duration}
            }
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed: {e}")
            return {
                "success": False,
                "tool": tool_name,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
