import json
from automation.registry import ToolRegistry
from automation.executor import ToolExecutor
from automation.tools import register_builtin_tools

# Ensure tools are registered
register_builtin_tools()


def test_registry_and_executor_basic():
    registry = ToolRegistry()
    assert "get_time" in registry.list_tools()
    executor = ToolExecutor(registry)

    # Successful execution
    res = executor.execute("get_time", {})
    assert res["success"] is True
    assert res["tool"] == "get_time"
    assert "date" in res["result"]

    # Unknown tool
    res2 = executor.execute("nonexistent_tool", {})
    assert res2["success"] is False
    assert res2["error"]["type"] == "ToolNotFound"


def test_api_execute_tool():
    from fastapi.testclient import TestClient
    import app

    client = TestClient(app.app)

    # Valid call
    r = client.post("/tools/execute", json={"tool": "get_time", "arguments": {}})
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is True
    assert j["tool"] == "get_time"

    # Missing tool
    r2 = client.post("/tools/execute", json={"arguments": {}})
    assert r2.status_code == 400

    # Unknown tool
    r3 = client.post("/tools/execute", json={"tool": "no_such_tool", "arguments": {}})
    assert r3.status_code == 404
