# MineClaw — Minecraft-as-a-Service API

## Overview
MineClaw is a Minecraft-as-a-Service platform. It runs a Minecraft server with a REST API that exposes game actions as tool calls. It contains zero AI logic — it is a pure execution layer. All AI reasoning happens on the client side (OpenClaw or any external AI).

The project also produces an **OpenClaw channel plugin** (`@openclaw/mineclaw`) that anyone can install to connect their OpenClaw instance to a MineClaw server.

## Architecture
- **PaperMC 1.21.11**: Minecraft server (port 25565)
- **bore**: TCP tunnel for external Minecraft client connections (bore.pub:PORT)
- **Bot Manager**: Node.js Express server (port 3001, localhost only) managing mineflayer bot instances
- **REST API**: Python FastAPI server (port 5000) — public-facing API with auth, proxies to bot manager, RCON for building
- **RCON**: localhost:25575 for server commands (fill, setblock, etc.)

## How It Works
1. External AI (OpenClaw) calls the MineClaw REST API with a Bearer token
2. API proxies bot operations to the Bot Manager on localhost:3001
3. Bot Manager creates/manages mineflayer bots that execute tool calls in Minecraft
4. Building commands go through RCON for fast bulk placement

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
- `POST /api/chat/send` — Send chat message in-game (for AI replies)

## Project Structure
```
├── mineclaw/
│   ├── api.py              # FastAPI REST API (port 5000)
│   ├── bot-manager.js      # Multi-bot manager (port 3001)
│   ├── rcon.py             # RCON client for server commands
│   └── package.json        # Node.js deps reference
├── minecraft-server/       # PaperMC server files
│   ├── server.jar
│   ├── server.properties
│   ├── start.sh
│   └── plugins/AIBuilder.jar
├── openclaw-plugin-mineclaw/   # OpenClaw channel plugin (npm package)
│   ├── package.json
│   ├── openclaw.plugin.json
│   ├── index.ts
│   ├── src/
│   │   ├── channel.ts      # ChannelPlugin implementation
│   │   ├── config-schema.ts
│   │   ├── outbound.ts     # Sends messages to Minecraft
│   │   ├── runtime.ts
│   │   ├── types.ts
│   │   └── webhook-server.ts  # Receives chat from MineClaw
│   └── skills/mineclaw/SKILL.md  # Bundled skill
├── bore                    # TCP tunnel binary
├── start-all.sh            # Master startup script (4 processes)
├── pyproject.toml          # Python dependencies
└── package.json            # Node.js dependencies
```

## OpenClaw Plugin
The `openclaw-plugin-mineclaw/` directory is an npm-publishable OpenClaw channel plugin. Users install it with:
```
openclaw plugins install @openclaw/mineclaw
```

It registers a `mineclaw` channel that:
- Starts a webhook HTTP server to receive player chat from the MineClaw server
- Sends AI responses back to Minecraft via the MineClaw REST API
- Bundles the MineClaw skill (bot control instructions) for the AI agent
- Supports per-account config (API URL, API key, webhook settings)

## Authentication
- Bearer token auth on all /api/* endpoints
- Token from MINECLAW_API_KEY env var
- All requests need `Authorization: Bearer <token>` header

## Available Bot Tools
navigate_to, navigate_to_player, look_around, get_position, check_inventory, scan_nearby_blocks, place_block, chat, wait, collect_nearby_items, equip_item, fly_to, teleport, give_item

## Server Settings
- Creative mode, superflat world, peaceful difficulty
- Max players: 5, Online mode: off
- RCON on port 25575 (password: minecraft-ai-builder)

## Chat Bridge
- Players type `!ai <message>` in Minecraft chat to talk to OpenClaw
- Bot-manager forwards chat events to the OpenClaw plugin webhook (OPENCLAW_WEBHOOK_URL)
- Plugin routes messages to the AI agent, AI replies go back via `/api/chat/send`
- Env vars needed on MineClaw server: OPENCLAW_WEBHOOK_URL, OPENCLAW_WEBHOOK_TOKEN

## Recent Changes
- 2026-02-15: Created OpenClaw channel plugin (@openclaw/mineclaw) — proper plugin installable via `openclaw plugins install`
- 2026-02-15: Added chat bridge — players can talk to OpenClaw via `!ai` in Minecraft chat
- 2026-02-15: Built MineClaw MVP — complete rewrite from AI-on-server to API-only architecture
- 2026-02-15: New REST API (FastAPI), multi-bot manager (mineflayer), OpenClaw skill
- 2026-02-15: Removed all server-side AI logic (chat_watcher, ai_providers, mc_builder, agent loop, boss_bar, build_book)
- 2026-02-15: 4 processes: PaperMC + bore + bot-manager + API (down from 5)
