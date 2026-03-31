# Lessons Learned

## 1. Never block the asyncio event loop in MCP tool handlers

**Context:** FastMCP's `Tool.run()` calls sync tool functions directly on the event loop — there is NO automatic thread offloading. If the tool function blocks (e.g., `subprocess.run()`, `time.sleep()`, file I/O), the entire MCP server becomes unresponsive.

**Fix:** Always declare tool handlers as `async` and use `anyio.to_thread.run_sync()` to offload blocking work:

```python
@mcp.tool()
async def my_tool(...):
    return await anyio.to_thread.run_sync(lambda: blocking_work(...))
```

## 2. `.venv` and `~/.cache/uv` permission issues

The `.venv` directory and `~/.cache/uv/archive-v0` were created with root ownership. This blocks `uv sync` and `uv lock --upgrade`. Fix requires `sudo chown -R $(whoami) .venv ~/.cache/uv`.

## 3. Cursor subagents generate extra billing requests

When using Cursor v2.4+, the agent automatically spawns **subagents** (Explore, Bash, Browser) that use `composer-1.5` by default, regardless of the selected model. Each subagent invocation costs extra requests (2 on legacy plans). This is NOT a plugin bug but Cursor's architecture. **Fix**: Add a Cursor Rule "Never invoke subagents" to `.cursor/rules/` or `~/.cursor/rules/`. The main agent retains all tool capabilities; it just runs them directly instead of delegating to subagents.

## 4. mcp library v1.8.0 BrokenResourceError bug

`mcp/server/stdio.py` `stdin_reader` only catches `ClosedResourceError` but not `BrokenResourceError`. This is a known issue (https://github.com/modelcontextprotocol/python-sdk/issues/564). Fixed in newer versions. Current installed: mcp 1.8.0, latest: 1.26.0.
