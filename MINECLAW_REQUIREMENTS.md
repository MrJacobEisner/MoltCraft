# MineClaw — Product Requirements Document

## Vision

MineClaw is a Minecraft-as-a-Service platform. It runs a Minecraft server with a REST API that exposes every possible game action as a tool call. It contains **zero AI logic** — it is a pure execution layer.

All AI reasoning happens on the client side: either through OpenClaw (texting commands via WhatsApp, Telegram, Discord, etc.) or through the `/mineclaw` command typed directly in Minecraft chat. In both cases, the AI runs externally and calls the MineClaw API to take actions in the game world.

Think of MineClaw as a "Minecraft operating system API" — it doesn't think, it just does what it's told.

---

## Key Architectural Principle

```
┌──────────────────────────────────────────────────────────┐
│                    CLIENT SIDE (AI lives here)            │
│                                                          │
│  ┌─────────────┐          ┌──────────────────────┐       │
│  │  OpenClaw    │          │  /mineclaw command    │      │
│  │  (WhatsApp,  │          │  (typed in Minecraft  │      │
│  │   Telegram,  │          │   chat, AI runs on    │      │
│  │   Discord)   │          │   user's OpenClaw)    │      │
│  └──────┬───────┘          └──────────┬───────────┘      │
│         │                             │                   │
│         │    AI reasoning, planning,  │                   │
│         │    tool selection all       │                   │
│         │    happen HERE              │                   │
│         └──────────┬──────────────────┘                   │
└────────────────────┼─────────────────────────────────────┘
                     │ HTTP API calls
                     ▼
┌──────────────────────────────────────────────────────────┐
│              MINECLAW SERVER (no AI, just execution)      │
│                                                          │
│  ┌──────────┐  ┌───────────┐  ┌────────────────┐        │
│  │ REST API │→ │Bot Manager│→ │ Mineflayer Bots│        │
│  │ (auth,   │  │(spawn,    │  │ (execute tool  │        │
│  │  routes) │  │ lifecycle)│  │  calls in MC)  │        │
│  └──────────┘  └───────────┘  └────────────────┘        │
│                                                          │
│  ┌──────────┐  ┌───────────┐  ┌────────────────┐        │
│  │ World    │  │  RCON     │  │  PaperMC       │        │
│  │ Manager  │  │  Client   │  │  Server        │        │
│  └──────────┘  └───────────┘  └────────────────┘        │
│                                                          │
│  No AI integrations. No LLM calls. No agent loops.       │
│  Pure tool execution + game state reporting.              │
└──────────────────────────────────────────────────────────┘
```

**MineClaw server has NO AI dependencies.** No Anthropic, no OpenAI, no Gemini API keys. No agent loops. No prompt engineering. No token counting. It is a stateless tool execution service.

**All intelligence lives on the client side.** OpenClaw runs its own AI (Claude, GPT, Gemini — whatever the user configures) and calls MineClaw's API to take actions. The `/mineclaw` in-game command forwards to the user's OpenClaw instance which then calls back to the API.

---

## Core Concepts

### Players & Bots
- **Human players** connect via standard Minecraft client
- **MineClaw bots** are mineflayer-based player entities that execute tool calls from the API
- Each bot has a unique username, its own inventory, position, and state
- Bots are dumb puppets — they do exactly what the API tells them to, nothing more
- Bots persist across human player sessions (keep existing until despawned)
- Multiple bots can coexist in the same world

### Worlds & Sessions
- The server has a **hub/lobby** world where players spawn initially
- Users can **create private worlds** via the API
- Each world has its own settings (creative or survival mode)
- Worlds persist on disk and can be started/stopped on demand
- Bots are assigned to specific worlds

### Game Modes

#### Creative Mode
- World is in creative mode (players can fly, have unlimited blocks)
- Bots have access to creative-specific tools: fly, teleport, place any block, fill regions, give items
- Building tools are available: place individual blocks, fill rectangular regions with `/fill` commands via RCON
- The AI on the client side (OpenClaw) decides what to build and sends block-by-block or region commands through the API
- Best for: building, designing, prototyping, artistic projects

#### Survival Mode
- World is in survival mode (health, hunger, mining, crafting, mobs)
- Bots play like real survival players: mine blocks, smelt ores, craft tools, fight mobs, eat food, manage health
- No creative shortcuts — everything must be gathered and crafted
- Pathfinding, combat, resource gathering, base building all through tool calls
- Best for: autonomous survival gameplay, resource farming, base building, exploration

---

## Two Entrypoints for AI

### 1. OpenClaw (External — Primary)
- User installs the MineClaw skill on their OpenClaw instance
- User texts their OpenClaw on WhatsApp/Telegram/Discord: "build me a castle"
- OpenClaw's AI reasons about the task, plans steps, and calls MineClaw API endpoints
- OpenClaw handles all AI: model selection, planning, memory, context management
- MineClaw just executes the tool calls and returns results

### 2. /mineclaw Command (In-Game — Secondary)
- Player types `/mineclaw build a castle` in Minecraft chat
- The MineClaw plugin captures this and forwards it to the user's configured OpenClaw endpoint
- OpenClaw processes it exactly as if the user had texted it
- The response comes back as tool calls to the MineClaw API
- This is just a convenience bridge — the AI still runs on OpenClaw, not on MineClaw

**Both entrypoints result in the same thing:** an external AI making tool calls to the MineClaw REST API. MineClaw never runs AI itself.

---

## Architecture

### Components

#### PaperMC Server
- PaperMC 1.21.11 with Multiverse plugin for multi-world support
- Hub/lobby world as default spawn
- Per-user worlds created on demand with configurable game mode
- RCON enabled for server command execution (localhost only)
- Online mode off (bots connect locally; security via bore tunnel + random port)

#### MineClaw Plugin (Java)
- PaperMC plugin that handles the `/mineclaw` in-game command
- When player types `/mineclaw <prompt>`:
  1. Plugin looks up the player's OpenClaw webhook URL (configured via `/mineclaw config <url>`)
  2. Sends the prompt to that URL as an HTTP POST
  3. OpenClaw processes it and calls back to MineClaw API
  4. Results appear in-game
- Also registers `/mineclaw config`, `/mineclaw status`, `/mineclaw help`

#### REST API (Python — Flask or FastAPI)
- Authenticated HTTP API on port 5000 (or separate port)
- All endpoints require `Authorization: Bearer <token>` header
- Stateless — just translates API calls into mineflayer bot actions and RCON commands
- Returns structured JSON responses with game state

#### Bot Manager (Node.js)
- Spawns and manages multiple mineflayer bot instances
- Each bot:
  - Unique username
  - Assigned world
  - Inventory, position, health state
  - Connection status (connected, disconnected, reconnecting)
- Bot lifecycle: spawn → connect → idle → receiving tool calls → idle → ... → despawn
- Auto-reconnect on disconnect
- Limits: max bots per user (default: 3), per world (default: 10), total (default: 20)

#### World Manager
- Uses Multiverse plugin via RCON to create/delete/manage worlds
- Each world has configurable: game mode, difficulty, world type, seed
- Worlds persist on disk, can be loaded/unloaded on demand

#### Status Page
- Web dashboard showing:
  - Server status (online/offline)
  - Connection address (bore.pub:PORT)
  - Active worlds and their game modes
  - Active bots and their current tasks
  - Recent API activity log

---

## API Endpoints

### Authentication
```
POST /api/auth/register         — Create account, get API token
POST /api/auth/login            — Login, get API token
GET  /api/auth/me               — Get current user info
```

### Worlds
```
POST   /api/worlds              — Create a new world
GET    /api/worlds              — List user's worlds
GET    /api/worlds/:id          — Get world details (players, bots, settings)
DELETE /api/worlds/:id          — Delete a world
POST   /api/worlds/:id/start   — Start/load a world
POST   /api/worlds/:id/stop    — Unload a world
```

World creation payload:
```json
{
  "name": "my-base",
  "mode": "survival",
  "seed": "optional-seed",
  "difficulty": "normal",
  "world_type": "normal"
}
```

### Bots
```
POST   /api/bots                    — Spawn a new bot in a world
GET    /api/bots                    — List user's bots
GET    /api/bots/:id                — Get bot status (position, health, inventory)
DELETE /api/bots/:id                — Despawn/remove a bot
GET    /api/bots/:id/inventory      — Get detailed inventory
```

Bot spawn payload:
```json
{
  "world_id": "world-uuid",
  "name": "MyHelper"
}
```

### Tool Execution (The Core of MineClaw)

This is the main interface. OpenClaw calls these to make bots do things.

```
POST   /api/bots/:id/execute        — Execute a single tool call on a bot
POST   /api/bots/:id/execute-batch  — Execute multiple tool calls in sequence
GET    /api/bots/:id/observe        — Get full observation (position, surroundings, inventory, health, nearby entities)
```

Execute payload:
```json
{
  "tool": "mine_block",
  "input": {"x": 10, "y": -50, "z": 22}
}
```

Response:
```json
{
  "success": true,
  "result": {
    "mined": "iron_ore",
    "position": {"x": 10, "y": -50, "z": 22},
    "items_collected": ["raw_iron x1"],
    "duration_ms": 1200
  },
  "bot_state": {
    "position": {"x": 10, "y": -50, "z": 22},
    "health": 20,
    "food": 18
  }
}
```

Batch execute payload:
```json
{
  "tools": [
    {"tool": "navigate_to", "input": {"x": 10, "y": -50, "z": 22}},
    {"tool": "mine_block", "input": {"x": 10, "y": -50, "z": 22}},
    {"tool": "collect_nearby_items", "input": {}}
  ]
}
```

Observe response:
```json
{
  "position": {"x": 10.5, "y": -50, "z": 22.3},
  "health": 20,
  "food": 18,
  "inventory": [
    {"item": "stone_pickaxe", "count": 1, "slot": 0},
    {"item": "raw_iron", "count": 12, "slot": 1}
  ],
  "nearby_blocks": {
    "iron_ore": [{"x": 11, "y": -51, "z": 23}, {"x": 12, "y": -50, "z": 24}],
    "stone": 842,
    "dirt": 124
  },
  "nearby_entities": [
    {"type": "player", "name": "mortgageboy", "distance": 12.5},
    {"type": "zombie", "name": null, "distance": 28.0}
  ],
  "world": "my-base",
  "mode": "survival",
  "time_of_day": 6000,
  "weather": "clear"
}
```

### Building (Creative Mode)

For creative worlds, RCON-based building tools for large-scale placement:

```
POST /api/bots/:id/build/fill       — Fill a region with a block type
POST /api/bots/:id/build/setblock   — Set a single block
POST /api/bots/:id/build/fill-batch — Execute multiple fill commands
```

Fill payload:
```json
{
  "x1": 0, "y1": -60, "z1": 0,
  "x2": 10, "y2": -50, "z2": 10,
  "block": "minecraft:stone_bricks"
}
```

Fill-batch payload:
```json
{
  "commands": [
    {"x1": 0, "y1": -60, "z1": 0, "x2": 20, "y2": -55, "z2": 20, "block": "minecraft:stone_bricks"},
    {"x1": 1, "y1": -59, "z1": 1, "x2": 19, "y2": -55, "z2": 19, "block": "minecraft:air"},
    {"x1": 5, "y1": -60, "z1": 0, "x2": 7, "y2": -56, "z2": 0, "block": "minecraft:oak_door"}
  ]
}
```

This lets OpenClaw's AI generate fill commands and send them in bulk — the same building capability as before, but driven entirely from the client side.

---

## Available Bot Tools

### Common Tools (Both Modes)
| Tool | Parameters | Description |
|------|-----------|-------------|
| navigate_to | x, y, z | Pathfind to coordinates using A* |
| navigate_to_player | name | Pathfind to a named player |
| look_around | | Get visual observation of surroundings |
| get_position | | Get bot's current x, y, z |
| check_inventory | | List all inventory items |
| scan_nearby_blocks | block_type, radius | Find specific blocks nearby |
| chat | message | Send message in game chat |
| wait | seconds | Wait/idle for specified time |
| collect_nearby_items | | Pick up dropped items in range |
| equip_item | item | Equip item to main hand |

### Creative Mode Only
| Tool | Parameters | Description |
|------|-----------|-------------|
| fly_to | x, y, z | Fly to coordinates (creative flight) |
| teleport | x, y, z | Instant teleport |
| place_block | x, y, z, type | Place any block from creative inventory |
| set_block_area | x1,y1,z1, x2,y2,z2, type | Fill rectangular region (via RCON /fill) |
| give_item | item, count | Give self items from creative inventory |

### Survival Mode Only
| Tool | Parameters | Description |
|------|-----------|-------------|
| mine_block | x, y, z | Mine a specific block |
| mine_type | type, count | Mine N blocks of a type |
| craft_item | item, count | Craft items (needs materials + table) |
| place_block | x, y, z, type | Place a block from inventory |
| attack_entity | type | Attack nearest entity of type |
| eat | | Eat food from inventory |
| drop_item | item, count | Drop items on ground |
| toss_to_player | player, item, count | Throw items to a player |
| smelt | item, count, fuel | Use furnace to smelt |
| get_health | | Check health and hunger |
| sleep | | Sleep in nearest bed |

---

## OpenClaw Skill

### Skill Definition (SKILL.md)

```markdown
---
name: mineclaw
description: Control bots in a Minecraft server — build, mine, craft, explore, and survive. Supports creative and survival modes.
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

# MineClaw — Minecraft Bot Control

You can control bots in a Minecraft server. The bots are real player entities in the game world.

## Setup
- API URL is stored in MINECLAW_API_URL
- API key is stored in MINECLAW_API_KEY
- All API calls use Authorization: Bearer $MINECLAW_API_KEY header

## Capabilities
You can:
- Create and manage Minecraft worlds (creative or survival mode)
- Spawn bots that appear as real players in the game
- Execute tool calls on bots: navigate, mine, craft, place blocks, fight, build
- Observe the game world through bot eyes (surroundings, inventory, health)
- Build large structures in creative mode using fill commands

## Workflow
1. Call GET /api/worlds to see available worlds (or POST /api/worlds to create one)
2. Call POST /api/bots to spawn a bot in a world
3. Call GET /api/bots/:id/observe to see what the bot sees
4. Call POST /api/bots/:id/execute with tool calls to make the bot act
5. Repeat observe → execute → observe until the task is complete

## Important
- In survival mode, bots must mine resources and craft. No shortcuts.
- In creative mode, use /api/bots/:id/build/fill-batch for large structures.
- Always observe before acting — check inventory, surroundings, position.
- Bots have real pathfinding (A*) — navigate_to handles obstacles automatically.
- Report progress to the user after significant milestones.
```

### Example User Interactions

```
User (WhatsApp): "Create a new survival world called MyAdventure"
OpenClaw: → POST /api/worlds {name: "MyAdventure", mode: "survival"}
          → POST /api/bots {world_id: "...", name: "Helper_1"}
          "Created survival world 'MyAdventure' and spawned Helper_1.
           Server: bore.pub:12345. What should the bot do?"

User: "Tell my bot to find diamonds"
OpenClaw: → GET /api/bots/:id/observe
          → POST /api/bots/:id/execute {tool: "scan_nearby_blocks", input: {block_type: "diamond_ore", radius: 64}}
          → POST /api/bots/:id/execute {tool: "navigate_to", input: {x: ..., y: 11, z: ...}}
          → POST /api/bots/:id/execute {tool: "mine_type", input: {type: "diamond_ore", count: 8}}
          → POST /api/bots/:id/execute {tool: "collect_nearby_items", input: {}}
          "Helper_1 found and mined 8 diamonds at (142, 11, -89)!"

User: "Build me a house in creative"
OpenClaw: → POST /api/bots/:id/build/fill-batch {commands: [...walls, floor, roof, door...]}
          "Done! Built a cozy house — 12x10x6 blocks, oak wood with glass windows."

User (in Minecraft chat): "/mineclaw make a garden next to my house"
Plugin:  → POST to user's OpenClaw webhook
OpenClaw: → GET /api/bots/:id/observe (to see the house location)
          → POST /api/bots/:id/build/fill-batch {commands: [...flowers, path, fence...]}
          "Built a garden with flowers and a stone path next to your house!"
```

---

## /mineclaw In-Game Command

### Commands
```
/mineclaw <prompt>                   — Send a task to your OpenClaw (AI processes it externally)
/mineclaw config <openclaw_url>      — Set your OpenClaw webhook URL
/mineclaw config apikey <key>        — Set your OpenClaw API key for auth
/mineclaw status                     — Show your bots and their status
/mineclaw help                       — Show available commands
```

### How /mineclaw Works
1. Player types `/mineclaw build a tower`
2. MineClaw plugin reads player's configured OpenClaw webhook URL
3. Plugin sends HTTP POST to OpenClaw:
   ```json
   {
     "message": "build a tower",
     "player": "mortgageboy",
     "world": "creative-1",
     "mineclaw_api": "http://bore.pub:12345/api",
     "bot_id": "uuid-of-players-bot"
   }
   ```
4. OpenClaw receives it, reasons about it, and calls MineClaw API to execute
5. Results appear in-game through the bot's actions

**The AI never runs on MineClaw.** The plugin is just a forwarding bridge.

---

## Data Model

### User
```
id:             UUID
username:       string
api_key:        string (hashed)
openclaw_url:   string (optional — their OpenClaw webhook for /mineclaw command)
created_at:     timestamp
max_bots:       int (default: 3)
max_worlds:     int (default: 2)
```

### World
```
id:             UUID
owner_id:       UUID (ref: User)
name:           string
mode:           "creative" | "survival"
difficulty:     "peaceful" | "easy" | "normal" | "hard"
world_type:     "normal" | "flat" | "amplified"
seed:           string (optional)
status:         "active" | "stopped" | "creating" | "deleting"
created_at:     timestamp
folder_name:    string (on-disk directory)
```

### Bot
```
id:             UUID
owner_id:       UUID (ref: User)
world_id:       UUID (ref: World)
username:       string (in-game name)
status:         "spawning" | "idle" | "busy" | "disconnected" | "despawned"
position:       {x, y, z}
health:         float (survival only)
food_level:     float (survival only)
created_at:     timestamp
last_active:    timestamp
```

Note: No `model` field on Bot — bots don't run AI. No Task table — task management is the client's (OpenClaw's) responsibility.

---

## Security

### API Authentication
- Every API request requires `Authorization: Bearer <token>` header
- Tokens are UUID-based, stored hashed
- Rate limiting: 60 requests/minute per token
- Each token scoped to one user — can only access own worlds/bots

### Bot Security
- Mineflayer bot control is internal only
- External access only through the authenticated REST API
- Bots can only be controlled by their owner's API token

### Server Security
- Minecraft server behind bore tunnel with random port
- Online mode off (required for bot connections)
- RCON on localhost only
- No op permissions for bots — they play as regular players

### OpenClaw Communication
- /mineclaw command sends to user-configured webhook URL
- API key can be set for OpenClaw auth
- MineClaw never stores or processes AI prompts — just forwards

---

## What MineClaw Does NOT Do
- Run any AI models
- Store any API keys for AI providers
- Do any prompt engineering or tool-use reasoning
- Manage conversation context or memory
- Plan or decompose tasks
- Decide what actions to take

MineClaw is a **tool execution service**. It receives instructions and executes them. All intelligence is external.

---

## Deployment

### Development (Current — Replit)
- Single PaperMC server instance
- bore tunnel for external Minecraft client + API access
- REST API on port 5000
- Bot manager on port 3001 (localhost only, fronted by REST API)
- SQLite for user/world/bot state

### Production (Future)
- Dedicated VPS or cloud instance
- Proper domain with SSL (mineclaw.gg or similar)
- PostgreSQL for persistent state
- Multiple Minecraft server instances (one per world group)
- Monitoring and alerting
- Usage-based billing

---

## MVP Scope (Build First)

### Phase 1: Core API + Multi-Bot
1. REST API with token auth (register, login)
2. Multi-bot support (spawn/despawn/list)
3. Tool execution endpoint (execute single tool call, return result + bot state)
4. Observe endpoint (full world observation for AI context)
5. Single world (creative mode, flat)

### Phase 2: Building + Survival
1. Creative building endpoints (fill, setblock, fill-batch via RCON)
2. Survival mode tools (mine, craft, smelt, combat, health)
3. Multiverse world management (create/delete worlds, creative vs survival)

### Phase 3: OpenClaw Integration
1. OpenClaw skill package (SKILL.md + scripts)
2. /mineclaw in-game command with OpenClaw webhook forwarding
3. Publish to ClawHub
4. Documentation and setup guide

### Phase 4: Production
1. Persistent storage (PostgreSQL)
2. Domain + SSL
3. Rate limiting and abuse prevention
4. Multi-user stress testing
5. Monitoring dashboard

---

## Success Metrics
- OpenClaw can control a MineClaw bot end-to-end with zero AI on the server
- A user can text "build me a house" on WhatsApp and see it built in Minecraft
- A survival bot can mine, craft, and build through pure API tool calls
- 10+ bots can operate simultaneously without server lag
- API response time under 500ms for tool execution
- Zero AI dependencies in MineClaw's codebase
