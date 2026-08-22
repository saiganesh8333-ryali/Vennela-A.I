from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from .executor import ToolExecutor
from .registry import ToolRegistry

router = APIRouter()

executor = ToolExecutor(ToolRegistry())


from typing import Optional

class ToolExecuteRequest(BaseModel):
    tool: Optional[str] = None
    arguments: Dict[str, Any] = {}


@router.post("/execute")
async def execute_tool(req: ToolExecuteRequest):
    if not req.tool:
        raise HTTPException(status_code=400, detail="'tool' is required")
    result = executor.execute(req.tool, req.arguments)
    if result.get("success"):
        return result
    else:
        # Map known error types to HTTP codes
        err = result.get("error", {})
        if err.get("type") == "ToolNotFound":
            raise HTTPException(status_code=404, detail=err.get("message"))
        elif err.get("type") == "InvalidArguments":
            raise HTTPException(status_code=400, detail=err.get("message"))
        elif err.get("type") == "PermissionError":
            raise HTTPException(status_code=403, detail=err.get("message"))
        else:
            raise HTTPException(status_code=500, detail=err.get("message", "Tool execution failed"))
