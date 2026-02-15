# MoltCraft — Minecraft Server + REST API

## Overview
MoltCraft is a Minecraft server with a REST API that exposes game actions as HTTP endpoints. AI agents (or any client) can spawn bots, move them around, build structures, and observe the world through the API. The server itself contains no AI logic — it is a pure execution layer.

## Architecture
- **PaperMC 1.21.11**: Minecraft server (port 25565)
- **bore**: TCP tunnel for external Minecraft client connections (bore.pub:PORT)
- **Bot Manager**: Node.js Express server (port 3001, localhost only) managing mineflayer bot instances
- **REST API**: Python FastAPI server (port 5000) — public-facing API with auth, proxies to bot manager, RCON for building

## How It Works
1. Client calls the REST API with a Bearer token
2. API proxies bot operations to the Bot Manager on localhost:3001
3. Bot Manager creates/manages mineflayer bots that execute tool calls in Minecraft
4. Building commands go through RCON for fast bulk placement

## Project Structure
```
├── mineclaw/
│   ├── api.py              # FastAPI REST API (port 5000)
│   ├── bot-manager.js      # Multi-bot manager (port 3001)
│   └── rcon.py             # RCON client for server commands
├── minecraft-server/       # PaperMC server files
│   ├── server.jar
│   ├── server.properties
│   └── start.sh
├── bore                    # TCP tunnel binary
├── start-all.sh            # Master startup script (4 processes)
├── pyproject.toml          # Python dependencies
└── package.json            # Node.js dependencies
```

## API Endpoints
- `GET /status` — HTML status page
- `GET /api/status` — JSON server status
- `GET /api/auth/me` — Verify auth token
- `POST /api/bots` — Spawn a bot
- `GET /api/bots` — List bots
- `GET /api/bots/{id}` — Get bot state
- `DELETE /api/bots/{id}` — Despawn bot
- `POST /api/bots/{id}/execute` — Execute a tool call on a bot
- `POST /api/bots/{id}/execute-batch` — Execute multiple tool calls sequentially
- `GET /api/bots/{id}/observe` — Get full world observation
- `POST /api/bots/{id}/build/setblock` — Place one block via RCON
- `POST /api/bots/{id}/build/fill` — Fill region via RCON
- `POST /api/bots/{id}/build/fill-batch` — Multiple fill commands
- `POST /api/chat/send` — Send chat message in-game via RCON

## Access Control
- No authentication required — API is open
- One bot per IP address enforced: each client IP can only have one active bot
- Clients can only control their own bot (ownership checked by IP)
- `GET /api/bots/me` — get your own bot's state based on your IP

## Available Bot Tools
navigate_to, navigate_to_player, look_around, get_position, check_inventory, scan_nearby_blocks, place_block, chat, wait, collect_nearby_items, equip_item, fly_to, teleport, give_item

## Server Settings
- Creative mode, superflat world, peaceful difficulty
- Max players: 5, Online mode: off
- RCON on port 25575 (password: minecraft-ai-builder)

## Recent Changes
- 2026-02-15: Codebase cleanup — stripped down to core (Minecraft server + REST API + bot manager)
- 2026-02-15: Removed OpenClaw plugin, chat bridge, old AI code, unused planning docs
- 2026-02-15: Removed unused dependencies (minecraft-protocol, prismarine-viewer)
