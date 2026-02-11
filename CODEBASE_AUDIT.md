# Codebase Audit Report

**Project:** Minecraft Java Server with AI Builder on Replit
**Date:** February 11, 2026
**Total Source Lines:** ~1,841 (Python: ~1,396, Bash: ~110, Java: ~188, HTML/CSS inline: ~190)

---

## Executive Summary

The codebase is a well-architected, purpose-built system that runs a Minecraft server with AI-powered building capabilities on Replit. It accomplishes something non-trivial: bridging four AI providers, a Minecraft server, a TCP tunnel, and a web status page through a clean multi-process orchestration. The code is functional, readable, and has clearly evolved through pragmatic iteration.

**Overall Grade: B+**

| Category | Score | Notes |
|----------|-------|-------|
| Functionality | A | All features work; retry system, cost tracking, fill optimization |
| Readability | B+ | Clean, linear code; some long functions could be split |
| Security | B | Good sandbox for AI code exec; some gaps in input handling |
| Error Handling | B | Consistent try/except with reconnection; some bare excepts |
| Performance | B+ | Fill optimizer is clever; batching is sensible |
| Maintainability | B- | Some duplication across providers; magic numbers; tight coupling |
| Architecture | B | Clean separation of concerns; IPC via filesystem is pragmatic but fragile |
| Test Coverage | F | Zero tests anywhere in the project |

---

## File-by-File Analysis

### 1. `ai-builder/mc_builder.py` (321 lines)

**Quality: B+**

Strengths:
- Clean API design with intuitive method names (`place_block`, `fill`, `cylinder`, `sphere`, etc.)
- Bounds checking via `_check_radius` and `_check_dimension` prevents runaway builds
- The fill-region optimizer (`_optimize_fill_regions`) is an effective greedy algorithm that reduces thousands of individual block placements into far fewer `/fill` commands
- Block state strings (e.g., `oak_door[half=lower]`) pass through correctly to RCON commands

Issues found:
- **`block_count` vs `len(self.blocks)` drift**: `_add_block` increments `self.block_count` on every call, but blocks are stored in a dict keyed by position. If two blocks are placed at the same position (overwrite), `block_count` will be inflated while `len(self.blocks)` gives the true count. `get_block_count()` returns `len(self.blocks)` (correct), but `self.block_count` is a misleading dead variable.
- **`fill_replace` ignores `replace_block` parameter**: The method signature accepts `replace_block` but never uses it. This is a silent API contract violation — AI-generated code calling `fill_replace(x1,y1,z1,x2,y2,z2, "stone", "dirt")` would silently ignore the replacement filter.
- **`arc` method only handles axis="y"**: Unlike `circle` which handles x/y/z axes, `arc` only implements the y-axis case. The other axes silently produce no output.
- **No block name validation**: Any string passes through as a block name. `builder.place_block(0,0,0, "not_a_real_block")` generates a `/setblock` command that fails at runtime with no prior warning.
- **`_optimize_fill_regions` is O(n^2) worst-case**: The sorted iteration + per-position membership checks in `remaining` (a set, so O(1) lookups) is efficient in practice, but the region expansion loops add overhead. For very large builds (50k+ blocks), this could become slow.

### 2. `ai-builder/chat_watcher.py` (633 lines)

**Quality: B**

Strengths:
- Thorough AST-based code safety validation (`SafetyValidator`) that blocks dangerous constructs before execution
- Comprehensive sandbox: restricted builtins, safe import mechanism, timeout via `SIGALRM`
- Retry system that feeds errors back to the AI for self-correction (up to 3 attempts)
- Detailed player-facing progress messages with token usage and cost reporting
- Clean command routing from both plugin queue (JSON files) and chat log parsing

Issues found:
- **`process_command` is 135 lines**: This function handles model resolution, AI generation, code extraction, execution, retry logic, progress messaging, stats reporting, and error recovery. It should be decomposed into smaller functions.
- **Sandbox escape vectors**: While the AST validator is good, there are potential gaps:
  - `type` is blocked but `isinstance` is allowed — `isinstance.__class__.__bases__` could theoretically reach object introspection
  - `str.format_map` is allowed (via generic string attrs) and could potentially access object attributes
  - The `visit_Attribute` check blocks `__` and `_` prefixed attrs, but doesn't block chained attribute access like `builder.__class__`... wait, it does block `__class__` since it starts with `__`. This is actually fine.
- **`extract_code` fallback is fragile**: The non-regex fallback (lines 177-188) looks for lines starting with `import`, `builder.`, `for`, `bx`, `by`, `bz` — this is brittle and could match non-code content or miss valid code that starts differently.
- **`SIGALRM` is Unix-only**: Not an issue on Replit (Linux), but makes the code non-portable.
- **Bare `except Exception` blocks**: Multiple places catch `Exception` broadly, which can mask bugs. For example, lines 312-324 catch any exception during RCON command sending, including `KeyboardInterrupt` (actually no, that's `BaseException`).
- **Duplicate RCON reconnection logic**: The reconnect pattern (disconnect + connect in except) appears at lines 316-324, 523-527, and in `ensure_rcon`. This should be a method on `RconClient`.
- **JSON commands are not atomically written**: The plugin writes JSON files that the Python watcher reads. If the watcher reads a partially-written file (race condition), `json.load` will fail. The plugin should write to a temp file and rename (atomic on Linux).

### 3. `ai-builder/ai_providers.py` (346 lines)

**Quality: B-**

Strengths:
- Clean model registry pattern with alias resolution
- Rate limit retry via `tenacity` decorator with exponential backoff
- Cost calculation with per-model pricing table
- All four providers work through Replit AI Integrations (no raw API keys)

Issues found:
- **LSP errors on line 209**: `message.content[0].text` — the Anthropic SDK returns a union type for content blocks (`TextBlock | ThinkingBlock | ToolUseBlock | ...`). The code assumes the first block is always a `TextBlock`. If the model returns a thinking block first (Claude Opus with extended thinking), this will crash. Should filter for `TextBlock` type.
- **Duplicated provider call functions**: `call_claude`, `call_openai`, `call_gemini`, `call_openrouter` are 80% identical. The pattern (create client, make request, extract usage, return dict) is the same. This could be a single function with provider-specific configuration.
- **`resolve_model` repetition**: Four near-identical if/elif blocks. Could be a dict-of-dicts lookup.
- **`generate_build_script` is a manual dispatch**: Four if/elif branches that map strings to functions. Could be a dict dispatch: `{"claude": call_claude, ...}[provider](model, prompt)`.
- **`get_available_models_text` uses `!` prefix**: This function still references the old `!command` syntax (e.g., `!claude <prompt>`) instead of the current `/command` syntax. This is stale/dead code that's inconsistent with the rest of the system.
- **Gemini doesn't use proper system prompt**: Gemini concatenates the system prompt with the user prompt as a single string, rather than using a system instruction parameter. This may reduce prompt effectiveness.
- **No token limit handling**: If the AI generates a response that exceeds `max_tokens`, the code may silently truncate, resulting in incomplete Python code that fails to parse.
- **`call_openrouter` uses `max_tokens` while `call_openai` uses `max_completion_tokens`**: This inconsistency may cause issues depending on OpenRouter's API compatibility layer.

### 4. `ai-builder/rcon_client.py` (96 lines)

**Quality: B+**

Strengths:
- Clean, minimal RCON protocol implementation
- Auto-reconnection with configurable retries
- Exact-length receive (`_recv_exact`) handles partial reads correctly
- Packet size validation (4096 max) prevents memory issues

Issues found:
- **LSP warnings on `self.sock`**: `sendall` and `recv` called on potentially `None` socket. The code works because `command()` calls `connect()` if `sock` is None, but the type checker can't verify this. A simple `assert self.sock` or null check would fix it.
- **Hardcoded RCON password in default**: `"minecraft-ai-builder"` appears both here and in `server.properties`. Should come from a single source (env var already supported but default is hardcoded in two places).
- **`send_commands` method is unused**: This method duplicates functionality that `chat_watcher.py` implements inline with its own batching logic. Dead code.
- **No connection pooling or keepalive**: Each command goes through the retry loop. If the connection is healthy, this is fine, but there's no heartbeat mechanism — a silently dead TCP connection will only be detected on the next command attempt.
- **`request_id` monotonically increases forever**: While unlikely to cause issues (Python ints have arbitrary precision), the RCON protocol uses a 32-bit signed int. After 2^31 requests, this will overflow in the struct.pack.

### 5. `status-page/server.py` (329 lines)

**Quality: B-**

Strengths:
- Clean dark-theme UI with auto-refresh
- Log redaction (IP addresses, login events) for privacy
- Both HTML page and JSON API endpoint
- Cache-Control headers properly set

Issues found:
- **Massive inline HTML/CSS/JS string**: 190+ lines of HTML embedded in a Python f-string with double-brace escaping everywhere. This is the single worst maintainability issue in the codebase. Should be a separate HTML template file.
- **Bare `except:` clauses**: Lines 26, 40, 49, 70 use bare `except:` which catches `SystemExit`, `KeyboardInterrupt`, and everything else. Should be `except Exception:` at minimum.
- **`subprocess.run` for log reading**: Using `tail` via subprocess is fine but adds process overhead on every status page load. Could read the file directly in Python.
- **No request rate limiting**: Every page load triggers file reads + subprocess calls + socket probes. A flood of requests could impact the Minecraft server's resources.
- **`check_port` doesn't verify Minecraft protocol**: It only checks if TCP port 25565 is accepting connections, not whether the Minecraft server is actually ready to accept players.
- **XSS vulnerability in logs**: Log content is inserted into HTML without escaping. If a player's chat message contains `<script>`, it would be rendered in the status page. The `logs` variable goes directly into `{logs}` in the HTML template.

### 6. `start-all.sh` (87 lines)

**Quality: B+**

Strengths:
- Clean process lifecycle management with trap/cleanup
- Bore tunnel address extraction from stdout via pipe
- Port-wait loops before starting dependent services
- All processes properly backgrounded with PID tracking

Issues found:
- **Bore subshell PID capture is misleading**: `BORE_PID=$!` captures the PID of the `while IFS= read` pipe consumer, not the bore tunnel process itself. The actual bore process runs inside a subshell within the pipe producer. This means `kill $BORE_PID` may not cleanly terminate the bore tunnel.
- **No health monitoring**: If the Minecraft server crashes mid-session, no process restarts it. The `wait -n` loop detects process exit but doesn't attempt recovery.
- **No bore reconnection**: If the bore tunnel drops (network blip), it stays dead until manual restart. A wrapper loop that restarts bore on exit would improve reliability.
- **Port wait loops have no timeout**: If the Minecraft server never starts (e.g., corrupt world), the bore and AI builder wait loops spin forever.

### 7. Java Plugin (`ai-builder-plugin/`) (188 lines total)

**Quality: B+**

Strengths:
- Clean separation into Plugin, CommandExecutor, and TabCompleter
- Proper JSON escaping in `writeToQueue`
- Tab completion with model variants and example prompts
- Minimal code that delegates all heavy lifting to the Python backend

Issues found:
- **Hand-rolled JSON serialization**: `String.format` with manual escaping (line 65-71) is fragile. If a player's prompt contains characters not covered by `escapeJson` (e.g., Unicode control characters), the JSON could be malformed. Should use a proper JSON library (Gson is included in Paper's runtime).
- **Non-atomic file writes**: `FileWriter` writes directly to the queue file. If the Python watcher reads mid-write, it gets partial JSON. Should write to a temp file and rename.
- **Timestamp-based filenames can collide**: Two rapid commands in the same millisecond would overwrite each other. Should append a random suffix or use `AtomicInteger`.
- **`AITabCompleter` doesn't filter by partial input for subsequent args**: Tab completion only works for the first argument. Typing `/claude :sonnet build a` and pressing tab gives nothing — multi-word prompt completion could be useful.

---

## Cross-Cutting Concerns

### Security Assessment

| Risk | Severity | Details |
|------|----------|---------|
| Code execution sandbox | Medium | AST-based validation is good but not bulletproof. The `exec()` call runs AI-generated code with restricted builtins. Edge cases in Python's object model could potentially escape the sandbox. |
| RCON password in plaintext | Low | Password `minecraft-ai-builder` is in `server.properties` and `rcon_client.py`. On Replit, this is internal-only so low risk, but it's still a plaintext secret in source control. |
| XSS in status page | Medium | Log content rendered without HTML escaping. A crafted chat message could inject JavaScript into the status page. |
| JSON injection in plugin | Low | Hand-rolled JSON escaping might miss edge cases. Malformed JSON would cause the Python watcher to skip the command (fail-safe). |
| No player authentication for AI commands | Low | Any player who joins can use AI commands and incur API costs. No rate limiting per player. |

### Performance Assessment

| Component | Assessment |
|-----------|-----------|
| Fill optimizer | Effective greedy algorithm. Reduces 1000s of blocks to 10s-100s of commands. Not optimal (NP-hard to find minimum rectangles) but good enough. |
| RCON batching | 50 commands per batch with 50ms sleep. Reasonable balance between speed and server load. |
| Command cap | 5,000 command limit prevents extreme builds from hanging the server. |
| Status page | No caching — every request does file I/O + subprocess + socket probe. Fine for low traffic. |
| Chat log polling | `readline()` with 200ms sleep loop. Low overhead but not instant. |
| Plugin queue polling | File system polling with `os.listdir` every loop iteration. Simple and reliable. |

### Code Duplication

| Pattern | Locations | Impact |
|---------|-----------|--------|
| AI provider call functions | `call_claude`, `call_openai`, `call_gemini`, `call_openrouter` | 4 functions that are ~80% identical |
| Model resolution | `resolve_model()` — 4 identical if/elif blocks | Could be a single dict lookup |
| RCON reconnection | `chat_watcher.py` lines 316-324, 523-527; `ensure_rcon` | Should be a `RconClient` method |
| Status badge HTML | Server-side and client-side badge rendering | Duplicated in initial HTML and JS refresh |

---

## Potential Architectural Improvements

### Priority 1 — High Impact, Low Effort

1. **Fix the XSS vulnerability in the status page**: HTML-escape log content before inserting into the template. One line: `import html; logs = html.escape(logs)`.

2. **Fix the Anthropic content block type assumption**: Filter `message.content` for `TextBlock` type instead of blindly accessing `[0].text`. Prevents crash when Claude returns thinking blocks.

3. **Add atomic file writes in the Java plugin**: Write to `cmd_<timestamp>.tmp`, then rename to `cmd_<timestamp>.json`. Prevents race conditions with the Python queue reader.

4. **Extract HTML template from `status-page/server.py`**: Move the 190-line HTML string to a separate `template.html` file. Massive readability improvement with zero functionality change.

5. **Remove the dead `block_count` instance variable**: `MinecraftBuilder.block_count` drifts from reality on overwrites. Remove it and rely solely on `get_block_count()` which uses `len(self.blocks)`.

### Priority 2 — Medium Impact, Medium Effort

6. **Unify AI provider calls into a single dispatcher**: Create a provider config dict and a single `call_provider(provider, model, prompt)` function. Eliminates ~100 lines of duplication across four provider functions.

7. **Decompose `process_command` in `chat_watcher.py`**: Split the 135-line function into smaller functions: `resolve_and_validate_model()`, `generate_with_retries()`, `report_build_stats()`. Improves testability and readability.

8. **Add per-player rate limiting**: Track last command time per player. Prevent a single player from spamming expensive AI builds. A simple dict with cooldown (e.g., 30s between builds) would suffice.

9. **Add bore tunnel auto-reconnection**: Wrap the bore process in a restart loop in `start-all.sh`. If bore exits, wait 5s and restart. The tunnel port changes each time, but the status page already handles dynamic addresses.

10. **Add port-wait timeouts**: The bore and AI builder wait loops in `start-all.sh` should have a maximum wait time (e.g., 120s) with a clear error message if the Minecraft server fails to start.

### Priority 3 — Architectural / Long-term

11. **Replace filesystem-based IPC with a proper queue**: The current plugin-to-Python communication uses JSON files on disk. This works but is inherently racy and doesn't scale. Options:
    - Use the Minecraft server's RCON to signal the Python backend (already connected)
    - Use a Unix domain socket or named pipe
    - Use SQLite as a lightweight queue

12. **Add a test suite**: Zero tests currently exist. Key testable units:
    - `MinecraftBuilder` geometry methods (sphere, cylinder, etc.) — verify correct block positions
    - `_optimize_fill_regions` — verify region merging correctness and command count reduction
    - `SafetyValidator` — verify that dangerous code is rejected and safe code passes
    - `extract_code` — verify code extraction from various AI response formats
    - `RconClient` packet encoding/decoding — unit test the protocol implementation

13. **Add structured logging**: Replace `print(f"[AI Builder] ...")` with Python's `logging` module. Would enable log levels, file output, and easier debugging. Currently all output goes to stdout, mixed with Minecraft server output.

14. **Add a build history/undo system**: Track placed blocks per build so players can `/undo` the last AI build. The `MinecraftBuilder` already has all block positions — saving them to a file or in-memory list would enable clearing them with air blocks.

15. **Make the fill optimizer smarter**: The current greedy algorithm (expand X, then Z, then Y) produces valid but not minimal regions. A more sophisticated approach could:
    - Try multiple starting axes and pick the best result
    - Use a sweep-line algorithm for better region decomposition
    - Pre-sort blocks into layers and optimize 2D slices first
    - The current approach is good enough for most builds, so this is low priority.

16. **Add Minecraft server health monitoring**: If the Minecraft server crashes or becomes unresponsive, the system currently does nothing. A health check loop that monitors the process and RCON responsiveness could auto-restart the server or alert via the status page.

17. **Support concurrent builds**: Currently, if two players issue build commands simultaneously, they're processed sequentially (single-threaded poll loop). For a 5-player server this is acceptable, but a threading or asyncio approach would prevent one large build from blocking others.

18. **Validate block names against a known list**: The `MinecraftBuilder` accepts any string as a block name. Validating against a list of known Minecraft block IDs before sending commands would catch AI hallucinations (e.g., `minecraft:magic_block`) earlier and produce better error messages.

---

## LSP Diagnostics Summary

7 diagnostics across 2 files (all non-blocking):

- **`ai_providers.py`** (5 warnings): Anthropic SDK union type — `message.content[0]` could be `ThinkingBlock`, `ToolUseBlock`, etc. Code works at runtime because Claude defaults to `TextBlock`, but is technically type-unsafe.

- **`rcon_client.py`** (2 warnings): `self.sock` could be `None` when calling `.sendall()` and `.recv()`. Code works because `command()` ensures connection, but the type checker can't verify the call flow.

---

## Dead Code Inventory

| Item | Location | Notes |
|------|----------|-------|
| `self.block_count` | `mc_builder.py:14` | Accumulator that drifts from reality; `get_block_count()` uses `len(self.blocks)` instead |
| `send_commands()` | `rcon_client.py:81-96` | Never called anywhere; chat_watcher implements its own batching |
| `get_available_models_text()` | `ai_providers.py:317-346` | Uses old `!command` syntax; never called in current code |
| `main.py` | Root directory | Boilerplate stub from Replit template; not used |
| `fill_replace` `replace_block` param | `mc_builder.py:77` | Parameter accepted but ignored |

---

## Conclusion

This is a solid hobby/prototype project that achieves its goals effectively. The architecture is pragmatic — filesystem IPC, polling loops, and inline HTML are all reasonable choices for a 5-player Minecraft server running on Replit. The AI sandbox is thoughtfully designed with multiple layers of protection. The fill-region optimizer is a clever optimization that makes a real difference in build speed.

The highest-priority fixes are the XSS vulnerability in the status page, the Anthropic content block type safety issue, and the non-atomic file writes in the plugin queue. Beyond those, the codebase would benefit most from reducing duplication in the AI provider layer and adding even basic tests for the core builder and sandbox logic.
