# Interactive Feedback MCP - Progress

## Task: Fix MCP server crash (BrokenResourceError)

**Problem:** After the `interactive_feedback` tool returns, the MCP server crashes with `anyio.BrokenResourceError` in `mcp/server/stdio.py` `stdin_reader`. Cursor shows "Not connected" on subsequent attempts.

**Root Cause:**
1. The `interactive_feedback` tool handler was a **sync function** calling `subprocess.run()` which blocks for minutes while the UI is open
2. FastMCP's `Tool.run()` method calls sync functions directly on the event loop (no thread offloading)
3. This blocks the asyncio event loop completely, preventing the MCP server from processing any incoming messages
4. When Cursor sends a cancellation request during the block, it piles up
5. After the subprocess returns, the session state is inconsistent — `stdin_reader` hits `BrokenResourceError` which is uncaught in `mcp` v1.8.0

**Fix Applied:**
- [x] Made `interactive_feedback` an `async` function
- [x] Used `anyio.to_thread.run_sync()` to offload the blocking `subprocess.run()` to a thread
- [x] This keeps the asyncio event loop free to process messages while the UI is open

**Pending (requires sudo):**
- [ ] Fix root-owned `.venv` and `~/.cache/uv/archive-v0` permissions
- [ ] Upgrade `mcp` 1.8.0 → 1.26.0 and `fastmcp` 2.3.0 → 3.1.0 (upstream `BrokenResourceError` catch fix)

---

## Task: Investigate Extra composer-1.5 Requests in Billing

**Problem:** User noticed that a single request generates multiple billing entries, with extra `composer-1.5` model requests appearing alongside the selected `claude-4.6-opus-high-thinking` model.

**Root Cause:** NOT a bug in the interactive-feedback-mcp plugin. This is Cursor's built-in **subagent architecture** (introduced in v2.4, Jan 2026). Cursor automatically spawns Explore/Bash/Browser subagents using `composer-1.5` for cost efficiency and context isolation.

**Key Findings:**
- [x] Confirmed: Subagents (Explore, Bash, Browser) use composer-1.5 by default
- [x] Confirmed: Thinking model variants count as 2 requests on legacy plans
- [x] Confirmed: No built-in toggle to disable subagents in Cursor settings
- [x] Found: Cursor official support recommends adding a Rule "Never invoke subagents"
- [x] Confirmed: Disabling subagents does NOT disable functionality — main agent runs tools directly

**Fix Applied:**
- [x] Added project-level rule: `.cursor/rules/no-subagents.mdc`
- [x] Added global user-level rule: `~/.cursor/rules/no-subagents.mdc`
- Rule instructs agent to avoid spawning subagents unless explicitly requested by user

---

## Task: UI Beautification & Window Adaptive

**Changes Applied:**

1. **Catppuccin Mocha dark theme via QSS** - replaced bare QPalette with comprehensive stylesheet
   - [x] Rounded corners on all inputs, buttons, group boxes (border-radius: 6-8px)
   - [x] Blue accent color (#89b4fa) for focus states, primary buttons, links
   - [x] Hover/pressed effects on all interactive elements
   - [x] Primary button style (blue) for Run and Submit
   - [x] Danger button style (red) for Stop
   - [x] Styled scrollbars (thin, rounded, matching theme)
   - [x] Better checkbox styling with custom indicator
   - [x] Named label styles: `#promptLabel`, `#pathLabel`, `#subtleLabel`

2. **Window adaptive fixes**
   - [x] Fixed bug in `_toggle_command_section`: `layout()` → `self.centralWidget().layout()`
   - [x] Better resize behavior using `sizeHint()` + `processEvents()`
   - [x] Improved spacing/margins (16px container, 12px between sections)

3. **Typography improvements**
   - [x] Console font size 9pt → 11pt
   - [x] Prompt label 14px with medium weight
   - [x] Path label in monospace 12px
   - [x] Subtle footer label 11px
