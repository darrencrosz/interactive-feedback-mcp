# Project Status - Work Log

## 2026-03-04: Fix MCP server crash after tool call

### Functions Implemented
- Modified `server.py`: changed `interactive_feedback` from sync to async function
- Added `anyio.to_thread.run_sync()` to offload blocking `subprocess.run()` to a worker thread
- Renamed `launch_feedback_ui` to `_launch_feedback_ui_sync` (private, sync helper)

### Errors Encountered
1. **Primary bug:** `anyio.BrokenResourceError` in `mcp/server/stdio.py` `stdin_reader` after tool returns
   - Caused by sync `subprocess.run()` blocking the asyncio event loop for minutes
   - MCP library v1.8.0 only catches `ClosedResourceError`, not `BrokenResourceError`

2. **Permission issues:** `.venv` and `~/.cache/uv/archive-v0` owned by root
   - Could not upgrade dependencies (mcp 1.8.0→1.26.0, fastmcp 2.3.0→3.1.0)
   - Reverted `uv.lock` to preserve working environment

### How We Solved
- Made tool handler async + `anyio.to_thread.run_sync()` — keeps event loop free
- Verified `anyio.to_thread.run_sync` is available in current env (anyio 4.9.0)
- Verified module loads correctly and tool function is recognized as async coroutine

### Execution Status
- **Code fix:** Successful (verified via syntax check + import test)
- **Dependency upgrade:** Blocked by permission issues (needs `sudo chown`)
