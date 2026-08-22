# Automation Level 1 — Usage and Action Format

This document describes the Level 1 Automation action format, available tools, arguments, and security restrictions.

Supported action structure

- Action JSON (simple):
  {
    "tool": "tool_name",
    "arguments": { ... }
  }

- The LLM may return a JSON object embedded in regular text; the adapter will extract the first valid JSON object that contains a `tool` key.

Available tools (Level 1)

- get_time
  - Arguments: none
  - Returns: { date, time, timezone }

- get_system_info
  - Arguments: none
  - Returns: { os, platform, architecture, python_version, hostname }

- open_url
  - Arguments: { "url": "https://example.com" }
  - Validation: only http/https allowed. The server validates the URL but does not open a browser in the production backend.

- open_app
  - Arguments: { "app_name": "name" }
  - Disabled by default. Requires the environment variable `ALLOWLISTED_APPS` (comma-separated) to include the app name. Returns a safe no-op in Level 1.

- list_files
  - Arguments: { "path": "relative/path" }
  - Lists entries under repository working directory; path traversal prevented via safe join.

- read_file
  - Arguments: { "path": "relative/path/to/file" }
  - Reads file under repo root with a size limit (200 KB) to avoid huge payloads.

- write_file
  - Arguments: { "path": "relative/path/to/file", "content": "..." }
  - Creates parent directories if needed and writes file. No destructive operations (delete) are provided in Level 1.

Security restrictions

- No arbitrary shell or subprocess execution. Tools are allowlisted and validated.
- Path traversal is prevented — tools operate relative to the repository working directory by default.
- open_app is disabled unless `ALLOWLISTED_APPS` is set.
- No secrets or API keys are read from requests or logged. Do not send secrets as tool arguments.

Examples

- Get time
  {
    "tool": "get_time",
    "arguments": {}
  }

- Read README
  {
    "tool": "read_file",
    "arguments": { "path": "README.md" }
  }

- Open a URL (validated only)
  {
    "tool": "open_url",
    "arguments": { "url": "https://example.com" }
  }

Notes

- The automation adapter used by `/chat` will look for JSON actions in the LLM response and, if found, call the ToolExecutor. The `/tools/execute` API route provides the same execution layer for programmatic use.
- This Level 1 design is intentionally conservative: it provides basic, safe tools and a stable execution path for future Level 2/3 enhancements.
