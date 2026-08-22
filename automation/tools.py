import os
import platform
import time
from typing import Dict, Any
from .registry import Tool, ToolRegistry
from urllib.parse import urlparse
import socket

REGISTRY = ToolRegistry()


def _safe_join(base: str, *parts) -> str:
    joined = os.path.abspath(os.path.join(base, *parts))
    if not joined.startswith(os.path.abspath(base)):
        raise ValueError("Path traversal detected")
    return joined


def get_time(_: Dict[str, Any]) -> Dict[str, Any]:
    now = time.localtime()
    tz = time.tzname[0] if time.tzname else ""
    return {
        "date": time.strftime("%Y-%m-%d", now),
        "time": time.strftime("%H:%M:%S", now),
        "timezone": tz
    }


def get_system_info(_: Dict[str, Any]) -> Dict[str, Any]:
    info = {
        "os": platform.system(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }
    try:
        info["hostname"] = socket.gethostname()
    except Exception:
        info["hostname"] = "unknown"
    return info


def open_url(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url")
    if not url:
        raise ValueError("'url' is required")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS URLs are allowed")
    # For safety do not actually open a browser in server environment
    return {"url": url, "opened": False, "note": "URL validated but not opened on server"}


def open_app(args: Dict[str, Any]) -> Dict[str, Any]:
    app_name = args.get("app_name")
    if not app_name:
        raise ValueError("'app_name' is required")
    # Level 1: do not execute arbitrary applications on the server.
    # Provide a safe response and allowlist mechanism for future phases.
    allowed = os.getenv("ALLOWLISTED_APPS", "").split(",") if os.getenv("ALLOWLISTED_APPS") else []
    if app_name not in allowed:
        raise PermissionError("Application not allowed or not configured in ALLOWLISTED_APPS")
    return {"app_name": app_name, "launched": False, "note": "App launching is disabled in Level 1 for server safety"}


def list_files(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", "")
    base = os.getcwd()
    target = _safe_join(base, path)
    if not os.path.exists(target):
        raise FileNotFoundError("Path does not exist")
    entries = []
    for name in os.listdir(target):
        p = os.path.join(target, name)
        entries.append({"name": name, "is_dir": os.path.isdir(p), "size": os.path.getsize(p)})
    return {"path": target, "entries": entries}


def read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        raise ValueError("'path' is required")
    base = os.getcwd()
    target = _safe_join(base, path)
    if not os.path.isfile(target):
        raise FileNotFoundError("File not found")
    # Limit file size read to avoid huge payloads
    size = os.path.getsize(target)
    if size > 200_000:  # 200 KB limit
        raise ValueError("File too large to read")
    with open(target, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"path": target, "content": content}


def write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    content = args.get("content", "")
    if not path:
        raise ValueError("'path' is required")
    base = os.getcwd()
    target = _safe_join(base, path)
    parent = os.path.dirname(target)
    if not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": target, "written_bytes": len(content)}


def register_builtin_tools():
    # Register tools but ignore duplicate registration attempts to be import-safe
    tools = [
        ("get_time", "Get current time and date", None, get_time),
        ("get_system_info", "Get system information", None, get_system_info),
        ("open_url", "Validate and open a URL (no-op on server)", {"required": ["url"]}, open_url),
        ("open_app", "Attempt to open an allowed application (disabled in Level 1)", {"required": ["app_name"]}, open_app),
        ("list_files", "List files under a path (restricted)", {"required": []}, list_files),
        ("read_file", "Read a file (restricted)", {"required": ["path"]}, read_file),
        ("write_file", "Write a file (restricted)", {"required": ["path","content"]}, write_file),
    ]

    for name, desc, schema, fn in tools:
        try:
            REGISTRY.register(Tool(name=name, description=desc, input_schema=schema, func=fn))
        except ValueError:
            # already registered - ignore
            pass


# Auto-register on import for convenience
try:
    register_builtin_tools()
except Exception:
    # Registration should be best-effort during import
    pass
