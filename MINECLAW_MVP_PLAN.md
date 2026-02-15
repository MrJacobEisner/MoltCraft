# MineClaw MVP — Implementation Plan

## Scope

Creative mode only. One world. OpenClaw as the sole AI entrypoint. No AI on the server.

The MVP proves one thing: **a user can text their OpenClaw "build me a castle" and see it appear in Minecraft.**

---

## What We're Building

```
User texts OpenClaw          OpenClaw calls MineClaw API         Bot acts in Minecraft
on WhatsApp/Discord    →     (spawn bot, observe, execute,  →   (place blocks, navigate,
                              fill regions)                      look around)
```

### In Scope
- REST API with token auth
- Single bot per user (spawn, despawn, observe, execute tools)
- Creative mode tool set (fly, teleport, place blocks, fill regions)
- RCON-based building (fill, setblock, fill-batch)
- OpenClaw skill (SKILL.md ready to drop into any OpenClaw instance)
- Status page showing server address + active bots

### Out of Scope (Future Phases)
- Survival mode
- Multi-world (Multiverse)
- /mineclaw in-game command (OpenClaw webhook bridge)
- Multiple bots per user
- Persistent database (SQLite/PostgreSQL)
- User registration UI
- Production deployment

---

## Architecture

```
Port 5000: MineClaw REST API (Python FastAPI)
           ├── /api/auth/*         — token management
           ├── /api/bots/*         — spawn/despawn/list bots  
           ├── /api/bots/:id/observe   — get full world observation
           ├── /api/bots/:id/execute   — execute a single tool call
           ├── /api/bots/:id/build/*   — creative building (fill, setblock)
           └── /status             — web status page (HTML)

Port 3001: Bot Manager (Node.js Express) — localhost only
           ├── POST /spawn         — create a new mineflayer bot
           ├── DELETE /despawn/:id — remove a bot
           ├── GET /bots           — list all active bots
           ├── GET /bots/:id       — get bot state
           ├── POST /bots/:id/execute  — execute tool on bot
           ├── GET /bots/:id/observe   — full observation
           └── GET /bots/:id/tools     — list available tools

Port 25565: PaperMC Minecraft Server
Port 25575: RCON (localhost only)
bore.pub:*: TCP tunnel for player connections
```

The REST API on port 5000 is the public-facing layer. It handles auth, validates requests, and forwards tool execution to the Bot Manager on port 3001. The Bot Manager is localhost-only and manages the actual mineflayer bot instances.

---

## Implementation Tasks

### Task 1: Refactor Bot Manager for Multi-Bot

**Current state:** bot.js creates a single hardcoded "ClaudeBot" on startup.

**Target state:** bot.js becomes a multi-bot manager that spawns/despawns bots on demand via HTTP API.

**File:** `ai-agent/bot.js` → rename to `mineclaw/bot-manager.js`

Changes:
- Remove hardcoded bot creation on startup
- Add `bots` map: `{ botId: { bot, username, status, tools } }`
- `POST /spawn` — accepts `{ username, world }`, creates mineflayer bot, returns `botId`
- `DELETE /despawn/:id` — disconnects and removes a bot
- `GET /bots` — returns list of `{ id, username, status, position, world }`
- `GET /bots/:id` — returns full bot state
- `POST /bots/:id/execute` — execute tool call on specific bot
- `GET /bots/:id/observe` — returns position, inventory, nearby blocks, entities, time, weather
- `GET /bots/:id/tools` — returns available tool definitions for this bot
- Keep existing tool implementations (navigate, look_around, scan, place_block, etc.)
- Add creative-mode tools: fly_to, teleport, give_item, set_block_area
- Each bot gets its own pathfinder Movements instance
- Bot auto-reconnect on disconnect (existing logic, per-bot)

### Task 2: Build REST API

**New file:** `mineclaw/api.py` (FastAPI)

This is the public-facing API. It handles auth and proxies to the Bot Manager.

**Auth:**
- Simple token-based auth for MVP
- On startup, generate a single admin API token and print it to console
- Store in memory (no database for MVP)
- All `/api/*` endpoints require `Authorization: Bearer <token>` header
- Token is also stored in an env var `MINECLAW_API_KEY` for easy OpenClaw config

**Endpoints:**

```python
# Auth
GET  /api/auth/me          → { username, token_valid }

# Bots
POST   /api/bots                → spawn bot, returns { id, username, status }
GET    /api/bots                → list bots [{ id, username, status, position }]
GET    /api/bots/{id}           → full bot state
DELETE /api/bots/{id}           → despawn bot

# Tool Execution  
POST   /api/bots/{id}/execute   → execute tool, returns { success, result, bot_state }
GET    /api/bots/{id}/observe   → full observation { position, inventory, nearby, entities, time, weather }

# Creative Building (RCON-based)
POST   /api/bots/{id}/build/setblock    → { x, y, z, block } → RCON setblock
POST   /api/bots/{id}/build/fill        → { x1,y1,z1, x2,y2,z2, block } → RCON fill  
POST   /api/bots/{id}/build/fill-batch  → { commands: [...] } → RCON fill batch

# Status
GET    /status              → HTML status page
GET    /api/status          → JSON { server_online, address, bots_active, world_mode }
```

**Implementation:**
- FastAPI app on port 5000
- Forwards bot operations to bot-manager on port 3001 via HTTP
- RCON client for build commands (fill, setblock)
- Serves status page HTML at /status
- CORS enabled for external access

### Task 3: Add Creative-Mode Tools to Bot Manager

New tools to add to the bot's tool set:

```javascript
// fly_to(x, y, z) — creative flight to coordinates
// Uses bot.creative.flyTo(goal) from mineflayer

// teleport(x, y, z) — instant teleport
// Sends /tp command via bot.chat("/tp ...")

// give_item(item, count) — give self items from creative inventory  
// Sends /give command via bot.chat("/give ...")

// set_block_area(x1,y1,z1, x2,y2,z2, block) — fill region
// This one goes through RCON, not mineflayer (handled by API layer)
```

### Task 4: Create OpenClaw Skill

**New directory:** `openclaw-skill/`

```
openclaw-skill/
├── SKILL.md              — Skill definition + instructions
└── scripts/
    └── mineclaw.sh       — Helper script for API calls (optional)
```

**SKILL.md contents:**
- Name: mineclaw
- Description: Control bots in a Minecraft server
- Required env: MINECLAW_API_URL, MINECLAW_API_KEY
- Tools: fetch
- Instructions:
  - How to spawn a bot
  - How to observe the world
  - How to execute tools (navigate, look, scan, place blocks)
  - How to build structures using fill-batch
  - Available tools list with parameters
  - Workflow: spawn → observe → plan → execute → observe → repeat
  - Building strategy: break structure into rectangular regions, use fill-batch
  - Always report progress to the user after milestones

### Task 5: Restructure Project & Update Startup

**Rename/reorganize:**
```
ai-agent/          → mineclaw/           (main MineClaw directory)
  bot.js           → bot-manager.js      (multi-bot manager)
  agent.py         → DELETE              (no more agent loop on server)
  api.py           → NEW                 (REST API)

ai-builder/        → KEEP for now        (RCON client reused by API)
  rcon_client.py   → mineclaw/rcon.py    (move RCON client)
  chat_watcher.py  → DELETE              (no more chat watching)
  ai_providers.py  → DELETE              (no AI on server)
  mc_builder.py    → DELETE              (building via API now)
  boss_bar.py      → DELETE              (no server-side builds)
  build_book.py    → DELETE              (no server-side builds)

ai-builder-plugin/ → KEEP for now        (will be replaced by MineClaw plugin later)

status-page/       → MERGE into api.py   (status page served by API)

openclaw-skill/    → NEW                 (OpenClaw skill package)

start-all.sh       → UPDATE              (start MC server, bore, bot-manager, API)
```

**start-all.sh processes:**
1. PaperMC Minecraft server (port 25565)
2. bore tunnel (TCP tunnel to bore.pub)
3. Bot Manager (Node.js, port 3001, localhost only)
4. MineClaw API (Python FastAPI, port 5000)

Only 4 processes instead of current 5. No chat watcher. No agent.

### Task 6: End-to-End Test with OpenClaw

Manual test flow:
1. Start MineClaw server
2. Copy API token from console output
3. Configure OpenClaw skill with API URL + token
4. Text OpenClaw: "spawn a bot in minecraft"
5. Verify bot appears in-game
6. Text: "look around and tell me what you see"
7. Verify observe returns world state
8. Text: "build a small house"
9. Verify fill-batch places blocks in-game
10. Text: "fly to coordinates 50, -50, 50"
11. Verify bot moves
12. Text: "despawn the bot"
13. Verify bot disconnects

---

## Available Creative Tools (Exposed via API)

| Tool | Parameters | Description |
|------|-----------|-------------|
| navigate_to | x, y, z | Pathfind walk to coordinates |
| fly_to | x, y, z | Creative flight to coordinates |
| teleport | x, y, z | Instant teleport |
| navigate_to_player | name | Walk to a named player |
| look_around | | Get surroundings description |
| get_position | | Get bot's x, y, z |
| check_inventory | | List inventory items |
| scan_nearby_blocks | block_type, radius | Find specific blocks nearby |
| place_block | x, y, z, type | Place a single block |
| give_item | item, count | Give self items (/give) |
| chat | message | Send in-game chat message |
| wait | seconds | Idle for a time |
| collect_nearby_items | | Pick up nearby drops |
| equip_item | item | Equip to main hand |

Building tools (RCON-based, via /api/bots/:id/build/*):

| Endpoint | Parameters | Description |
|----------|-----------|-------------|
| /build/setblock | x, y, z, block | Place one block via RCON |
| /build/fill | x1,y1,z1, x2,y2,z2, block | Fill region via RCON |
| /build/fill-batch | commands[] | Multiple fill commands at once |

---

## OpenClaw Skill Strategy

The skill is a SKILL.md file that teaches OpenClaw how to use the MineClaw API. Since OpenClaw skills work via natural language instructions + fetch tool, the skill just needs to:

1. Describe the API endpoints clearly
2. Explain the workflow (spawn → observe → execute → observe)
3. Give building strategies (decompose structures into fill regions)
4. List all available tools with their parameters

OpenClaw's AI (whatever model the user runs — Claude, GPT, Gemini) reads these instructions and figures out how to accomplish the user's request by making fetch() calls to the MineClaw API.

The skill does NOT contain any AI logic — it's just documentation that OpenClaw's AI reads.

---

## Key Technical Decisions

### Why FastAPI for the REST API?
- Already have Python in the environment
- Async support for handling multiple bot requests
- Auto-generated OpenAPI docs (useful for OpenClaw skill reference)
- Lightweight, fast startup

### Why keep Bot Manager as separate Node.js process?
- mineflayer is Node.js only — can't run in Python
- Separation of concerns: API handles auth/routing, Bot Manager handles Minecraft
- Bot Manager stays on localhost only (security)
- API proxies requests to Bot Manager

### Why not use the existing chat_watcher.py?
- chat_watcher polls a queue directory and watches log files — wrong pattern for an API
- MineClaw needs request/response (HTTP), not fire-and-forget (file queue)
- Clean break from the old architecture

### Why RCON for building instead of mineflayer?
- mineflayer's block placement is slow (one at a time with delays)
- RCON /fill command can place thousands of blocks in one call
- Already have a proven RCON client
- Creative mode building is fundamentally about server commands, not bot actions

### Auth approach for MVP
- Single API token generated on startup, printed to console
- Stored in MINECLAW_API_KEY env var
- No user registration, no database
- Good enough for personal use with OpenClaw
- Will be replaced with proper auth + DB in production phase

---

## What Gets Deleted

These files are no longer needed in the MineClaw architecture:

| File | Reason |
|------|--------|
| ai-builder/chat_watcher.py | Replaced by REST API |
| ai-builder/ai_providers.py | No AI on server |
| ai-builder/mc_builder.py | Building via RCON API endpoints |
| ai-builder/boss_bar.py | No server-side build process |
| ai-builder/build_book.py | No server-side build reports |
| ai-agent/agent.py | No agent loop on server |
| status-page/server.py | Merged into API |
| status-page/template.html | Merged into API |

### What Gets Kept/Reused
| File | Reuse |
|------|-------|
| ai-builder/rcon_client.py | Moved to mineclaw/rcon.py |
| ai-agent/bot.js | Refactored into mineclaw/bot-manager.js |
| minecraft-server/* | Unchanged |
| bore | Unchanged |
| start-all.sh | Updated for new process list |

---

## Estimated Effort

| Task | Complexity | Notes |
|------|-----------|-------|
| 1. Multi-bot manager | Medium | Refactor existing bot.js, add spawn/despawn/per-bot routing |
| 2. REST API | Medium | New FastAPI app, auth, proxy to bot manager, RCON building |
| 3. Creative tools | Small | Add fly_to, teleport, give_item to bot |
| 4. OpenClaw skill | Small | SKILL.md with API docs and instructions |
| 5. Restructure project | Small | Rename dirs, update start-all.sh, delete old files |
| 6. End-to-end test | Small | Manual test with OpenClaw |

Total: ~500-700 lines of new/refactored code. Most of the existing bot tool implementations carry over unchanged.
