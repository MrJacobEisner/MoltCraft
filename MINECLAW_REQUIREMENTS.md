# MineClaw — Requirements Document

## Vision

MineClaw is a Minecraft-as-a-Service platform that lets users control AI-powered bots in Minecraft worlds through OpenClaw (or any external agent framework). Users can text their OpenClaw bot on WhatsApp, Telegram, Discord, etc. and have it join a Minecraft server, build structures, mine resources, craft items, and play the game autonomously — even while the user is offline.

MineClaw is inspired by OpenClaw's architecture: planner/executor agent loops, JSONL transcript logging, context window management, and model failover — but purpose-built for the Minecraft domain.

---

## Core Concepts

### Players & Bots
- **Human players** connect via standard Minecraft client
- **MineClaw bots** are mineflayer-based player entities driven by AI agent loops
- Each bot has a unique username, its own inventory, position, and state
- Bots persist across human player sessions — they keep working when humans log off
- Multiple bots can coexist in the same world

### Worlds & Sessions
- The server has a **hub/lobby** world where players spawn initially
- Users can **create private worlds** (via API or in-game command)
- Each world has its own settings (creative or survival mode)
- Worlds persist on disk and can be started/stopped on demand
- Bots are assigned to specific worlds

### Game Modes

#### Creative Mode
- World is in creative mode (players can fly, have unlimited blocks)
- **AI Builder system is enabled**: bots can use /claude, /openai, /gemini, /deepseek, /kimi, /grok, /glm commands to generate and place structures via AI code generation
- Bots can also perform standard creative actions: fly, place blocks, teleport
- Best for: building, designing, prototyping, artistic projects
- AI builds at origin (0,0,0) and backend auto-offsets to player/bot position

#### Survival Mode
- World is in survival mode (health, hunger, mining, crafting, mobs)
- **AI Builder is disabled** — bots must gather resources and build by hand
- Bots play like a real survival player: mine blocks, smelt ores, craft tools, fight mobs, eat food, manage health
- Pathfinding, combat, resource gathering, base building all done step-by-step
- Best for: autonomous survival gameplay, resource farming, base building, exploration

---

## Architecture

### Layer 1: MineClaw Server Platform

The core platform running on Replit (or any host). Manages the Minecraft server, worlds, bots, and API.

#### Components

##### Minecraft Server (PaperMC)
- PaperMC 1.21.11 with Multiverse plugin for multi-world support
- Hub/lobby world (creative, flat) as default spawn
- Per-user worlds created on demand with configurable game mode
- RCON enabled for server command execution
- Online mode off (bots connect locally; security via bore tunnel + random port)

##### Bot Manager
- Spawns and manages multiple mineflayer bot instances
- Each bot has:
  - Unique username (e.g., "Bot_alice_1", "Bot_bob_2")
  - Assigned world
  - Current task (or idle)
  - Inventory state
  - Position
  - Connection status (connected, disconnected, reconnecting)
- Bot lifecycle: spawn → connect → idle → task → idle → ... → despawn
- Auto-reconnect on disconnect
- Max bots per user (configurable, default: 3)
- Max bots per world (configurable, default: 10)
- Max bots total on server (configurable, default: 20)

##### Agent Engine
- Runs the AI agent loop for each active bot
- OpenClaw-inspired architecture:
  - **Planner**: breaks complex tasks into subtasks
  - **Executor**: runs each subtask using bot tools
  - **Context Window Guard**: monitors token usage, triggers summarization before overflow
  - **JSONL Transcript Logger**: logs every reasoning step, tool call, and result
  - **Model Failover**: if primary model fails, falls back to alternatives
  - **Stuck-Loop Detector**: detects repeated failing actions and re-plans
- Supports both creative-mode tools (AI builder + flying + teleport) and survival-mode tools (mining + crafting + combat + hunger management)
- Max iterations per task: 50 (configurable)
- Task timeout: 10 minutes (configurable)

##### REST API
- Authenticated HTTP API for external agents (OpenClaw) and users
- All endpoints require API token in Authorization header
- Base URL exposed via bore tunnel or custom domain

##### Status Page
- Web dashboard showing:
  - Server status (online/offline)
  - Connection address (bore.pub:PORT)
  - Active worlds and their game modes
  - Active bots and their current tasks
  - Recent activity log

#### API Endpoints

##### Authentication
```
POST /api/auth/register    — Create account, get API token
POST /api/auth/login       — Login, get API token
GET  /api/auth/me          — Get current user info
```

##### Worlds
```
POST   /api/worlds              — Create a new world
GET    /api/worlds              — List user's worlds
GET    /api/worlds/:id          — Get world details
DELETE /api/worlds/:id          — Delete a world
POST   /api/worlds/:id/start   — Start/load a world
POST   /api/worlds/:id/stop    — Unload a world
```

World creation payload:
```json
{
  "name": "my-base",
  "mode": "survival",        // "creative" or "survival"
  "seed": "optional-seed",
  "difficulty": "normal",    // "peaceful", "easy", "normal", "hard"
  "world_type": "normal"     // "normal", "flat", "amplified"
}
```

##### Bots
```
POST   /api/bots                 — Spawn a new bot in a world
GET    /api/bots                 — List user's bots
GET    /api/bots/:id             — Get bot status, position, inventory
DELETE /api/bots/:id             — Despawn/remove a bot
POST   /api/bots/:id/task       — Give bot a task
GET    /api/bots/:id/task       — Get current task status
POST   /api/bots/:id/task/cancel — Cancel current task
GET    /api/bots/:id/inventory  — Get bot's inventory
GET    /api/bots/:id/transcript — Get bot's JSONL action transcript
```

Bot spawn payload:
```json
{
  "world_id": "world-uuid",
  "name": "MyHelper",         // optional custom name
  "model": "gemini-3-flash"   // AI model to use for agent loop
}
```

Task payload:
```json
{
  "task": "mine 64 iron ore and smelt it into iron ingots",
  "priority": "normal"        // "low", "normal", "high"
}
```

##### AI Builder (Creative Mode Only)
```
POST /api/build                — Trigger an AI build
GET  /api/build/:id/status    — Get build status
```

Build payload:
```json
{
  "world_id": "world-uuid",
  "prompt": "build a medieval castle with a moat",
  "model": "claude",          // "claude", "openai", "gemini", etc.
  "variant": "opus4.5",       // optional model variant
  "position": {"x": 0, "y": -60, "z": 0}  // optional, defaults to bot position
}
```

---

### Layer 2: OpenClaw Skill

A skill package that users install on their OpenClaw instance to control MineClaw.

#### Skill Definition (SKILL.md)
```
---
name: mineclaw
description: Control AI bots in Minecraft — build, mine, craft, explore, and survive
metadata:
  openclaw:
    emoji: ⛏️
    primaryEnv: MINECLAW_API_KEY
    requires:
      bins: []
      config:
        - api_url
        - api_key
tools:
  - fetch
---
```

#### Capabilities
The skill teaches OpenClaw how to:
- Create and manage Minecraft worlds
- Spawn and control bots
- Give bots tasks in natural language
- Check on bot progress and inventory
- Trigger AI builds (creative mode)
- Get status updates and transcripts

#### Example User Interactions (via WhatsApp/Telegram/Discord)
```
User: "Create a new survival world called MyAdventure"
Bot:  "Created survival world 'MyAdventure'. Server: bore.pub:12345. 
       Spawned your bot 'Helper_1'. What should it do?"

User: "Tell my bot to find diamonds"
Bot:  "Helper_1 is now mining. I'll update you when it finds diamonds."
[... 10 minutes later ...]
Bot:  "Helper_1 found 8 diamonds! It's at coordinates (142, 11, -89). 
       Want me to have it come back to base?"

User: "Build me a japanese temple in creative"
Bot:  "Switching to your creative world. Building a japanese temple now..."
Bot:  "Done! Built a 3-story japanese temple with cherry blossom trees.
       42x35x28 blocks, 3,847 blocks placed. Join to see it!"

User: "What's my bot doing right now?"
Bot:  "Helper_1 is idle in MyAdventure at (142, 11, -89). 
       Inventory: 8 diamonds, 32 iron ingots, 1 diamond pickaxe.
       Last task: 'find diamonds' (completed 2 hours ago)"
```

---

### Layer 3: Agent Engine (OpenClaw-Inspired)

The brain of each bot. Runs independently per bot.

#### Planner/Executor Architecture

```
Task: "mine 64 iron ore and smelt it into iron ingots"
         |
    [PLANNER] — breaks into subtasks:
         |
    1. Check inventory for pickaxe
    2. If no pickaxe, craft one (sub-plan: get wood → craft planks → sticks → pickaxe)
    3. Find iron ore (scan, navigate to caves/underground)
    4. Mine 64 iron ore
    5. Find or craft furnace
    6. Smelt iron ore into ingots
    7. Report completion
         |
    [EXECUTOR] — runs each subtask:
         |
    For each subtask:
      → Observe (look_around, check_inventory)
      → Reason (what tools/steps needed)
      → Act (mine, craft, navigate, etc.)
      → Verify (did it work?)
      → If failed: retry or escalate to planner for re-routing
```

#### JSONL Transcript Format
Each bot maintains a transcript file: `transcripts/{bot_id}_{date}.jsonl`

```jsonl
{"ts":"2026-02-15T12:00:01Z","type":"task_start","task":"mine 64 iron ore","player":"alice"}
{"ts":"2026-02-15T12:00:01Z","type":"plan","subtasks":["check pickaxe","find iron","mine 64","smelt"]}
{"ts":"2026-02-15T12:00:02Z","type":"thought","text":"I need to check if I have a pickaxe first"}
{"ts":"2026-02-15T12:00:02Z","type":"tool_call","tool":"check_inventory","input":{},"iteration":1}
{"ts":"2026-02-15T12:00:03Z","type":"tool_result","tool":"check_inventory","result":{"items":["stone_pickaxe x1"]},"duration_ms":450}
{"ts":"2026-02-15T12:00:03Z","type":"thought","text":"I have a stone pickaxe. Now I need to find iron ore underground."}
{"ts":"2026-02-15T12:00:04Z","type":"tool_call","tool":"scan_nearby_blocks","input":{"block_type":"iron_ore","radius":32},"iteration":2}
{"ts":"2026-02-15T12:00:05Z","type":"tool_result","tool":"scan_nearby_blocks","result":{"found":3,"nearest":{"x":15,"y":-48,"z":22}},"duration_ms":800}
{"ts":"2026-02-15T12:00:05Z","type":"subtask_complete","subtask":"find iron","status":"success"}
{"ts":"2026-02-15T12:01:30Z","type":"progress","message":"Mined 12/64 iron ore so far","subtask":"mine 64"}
{"ts":"2026-02-15T12:05:00Z","type":"task_complete","message":"Mined 64 iron ore and smelted into 64 iron ingots","success":true}
```

#### Context Window Guard
- Track approximate token count of conversation history
- When approaching 70% of model's context limit:
  - Ask AI to summarize progress so far into a compact memo
  - Replace old messages with the summary
  - Keep the most recent 10 messages intact
- This preserves task context without hard-truncation artifacts

#### Model Failover Chain
```
Primary:   gemini-3-flash-preview (fast, cheap)
Fallback1: gemini-2.5-flash (reliable)
Fallback2: claude-haiku-4-5 (if Gemini is down)
Fallback3: gpt-5-mini (last resort)
```
- On API error or rate limit: wait with exponential backoff
- After 3 consecutive failures on same model: switch to next in chain
- Log all failovers in transcript

#### Stuck-Loop Detection
- Track last N tool calls (window of 10)
- If same tool called 5+ times with same/similar input and same failing result → stuck
- On stuck detection:
  - Send chat message: "I seem to be stuck, re-planning..."
  - Return to planner with failure context
  - Planner generates alternative approach
  - If stuck 3 times on same subtask → mark subtask failed, move on or abort

---

## Bot Tool Sets

### Common Tools (Both Modes)
- navigate_to(x, y, z) — pathfind to coordinates
- navigate_to_player(name) — pathfind to a player
- look_around() — observe surroundings (blocks, entities, players nearby)
- get_position() — get bot's current coordinates
- check_inventory() — list inventory contents
- scan_nearby_blocks(type, radius) — find specific block types nearby
- chat(message) — send message in game chat
- wait(seconds) — wait/idle
- collect_nearby_items() — pick up dropped items
- equip_item(item) — equip item to hand
- task_complete(summary) — mark task as done
- task_failed(reason) — mark task as failed

### Creative Mode Tools
All common tools plus:
- place_block(x, y, z, type) — place a block
- ai_build(prompt, model) — trigger AI builder to generate a structure
- fly_to(x, y, z) — fly to coordinates (creative flight)
- teleport(x, y, z) — instant teleport
- set_block_area(x1, y1, z1, x2, y2, z2, type) — fill region with block type
- give_item(item, count) — give self items from creative inventory

### Survival Mode Tools
All common tools plus:
- mine_block(x, y, z) — mine a specific block
- mine_type(type, count) — mine N blocks of a type
- craft_item(item, count) — craft items (requires materials + crafting table)
- place_block(x, y, z, type) — place a block from inventory
- attack_entity(type) — attack nearest entity of type
- eat() — eat food from inventory
- drop_item(item, count) — drop items
- toss_to_player(player, item, count) — throw items to a player
- smelt(item, count, fuel) — use furnace to smelt
- get_health() — check health and hunger
- sleep() — sleep in nearest bed (skip night)

---

## Data Model

### User
```
id:         UUID
username:   string
api_key:    string (hashed)
created_at: timestamp
max_bots:   int (default: 3)
max_worlds: int (default: 2)
```

### World
```
id:          UUID
owner_id:    UUID (ref: User)
name:        string
mode:        "creative" | "survival"
difficulty:  "peaceful" | "easy" | "normal" | "hard"
world_type:  "normal" | "flat" | "amplified"
seed:        string (optional)
status:      "active" | "stopped" | "creating" | "deleting"
created_at:  timestamp
folder_name: string (on-disk directory)
```

### Bot
```
id:            UUID
owner_id:      UUID (ref: User)
world_id:      UUID (ref: World)
username:      string (in-game name)
model:         string (AI model for agent loop)
status:        "spawning" | "idle" | "working" | "disconnected" | "despawned"
current_task:  string (null if idle)
position:      {x, y, z}
health:        float (survival only)
food_level:    float (survival only)
created_at:    timestamp
last_active:   timestamp
```

### Task
```
id:            UUID
bot_id:        UUID (ref: Bot)
description:   string
status:        "queued" | "planning" | "executing" | "completed" | "failed" | "cancelled"
subtasks:      [{description, status, result}]
started_at:    timestamp
completed_at:  timestamp
result:        string
transcript:    string (path to JSONL file)
iterations:    int
tokens_used:   int
model_used:    string
```

---

## Security

### API Authentication
- Every API request requires `Authorization: Bearer <token>` header
- Tokens are UUID-based, stored hashed in database
- Rate limiting: 60 requests/minute per token
- Each token scoped to one user — can only access own worlds/bots

### Bot Security
- Bot HTTP API (mineflayer control) binds to localhost only
- External access only through the authenticated REST API
- Bots can only be controlled by their owner's API token

### Server Security
- Minecraft server behind bore tunnel with random port (changes each restart)
- Online mode off (required for bot connections)
- RCON on localhost only
- No op permissions for bots — they play as regular players

### OpenClaw Skill Security
- API key stored in OpenClaw's encrypted env vars
- All API calls over HTTPS (when deployed with proper domain)
- Skill does not store any data locally — all state is on MineClaw server

---

## Deployment

### Development (Current — Replit)
- Single PaperMC server instance
- bore tunnel for external access
- All components run as background processes via start-all.sh
- SQLite or in-memory for user/world/bot state (lightweight)

### Production (Future)
- Dedicated VPS or cloud instance
- Proper domain with SSL (mineclaw.io or similar)
- PostgreSQL for persistent state
- Redis for session management and task queues
- Multiple Minecraft server instances (one per world group)
- Container-based bot isolation
- Monitoring and alerting (bot health, server performance)
- Billing integration for compute/AI usage

---

## MVP Scope (Build First)

### Phase 1: Core Platform
1. REST API with token auth (register, login)
2. Multi-bot support (spawn/despawn/list bots)
3. Bot task API (send task, get status, cancel, get transcript)
4. Improved agent engine (planner/executor, JSONL logging, context guard)
5. Creative + survival mode tool sets

### Phase 2: World Management
1. Multiverse integration for multiple worlds
2. World CRUD API (create, list, delete, start, stop)
3. Per-world game mode (creative/survival)
4. Bot assignment to worlds

### Phase 3: OpenClaw Integration
1. OpenClaw skill package (SKILL.md + scripts)
2. Publish to ClawHub
3. Documentation and setup guide

### Phase 4: Production Hardening
1. Persistent storage (PostgreSQL)
2. Proper domain + SSL
3. Rate limiting and abuse prevention
4. Monitoring dashboard
5. Usage billing

---

## Success Metrics
- A user can install the MineClaw skill on OpenClaw in under 5 minutes
- A user can text "build me a house" on WhatsApp and see it built in Minecraft within 2 minutes
- A survival bot can autonomously mine, craft, and build a basic shelter
- 10+ bots can operate simultaneously without server lag
- Bot transcripts are human-readable and debuggable
- Zero security incidents from exposed APIs
