---
name: mineclaw
description: Control bots in a Minecraft server — build structures, navigate, explore, and create. Creative mode.
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

You control bots in a Minecraft server through a REST API. Bots are real player entities in a creative mode world. You send HTTP requests to spawn bots, observe the world through their eyes, execute tools (navigate, place blocks, fly), and build large structures using fill commands. The bots do exactly what you tell them — you handle all the planning and decision-making.

## Setup

- API URL is stored in `MINECLAW_API_URL` (e.g., `https://your-repl.replit.app` or the bore tunnel address)
- API key is stored in `MINECLAW_API_KEY`
- All API calls require the header: `Authorization: Bearer $MINECLAW_API_KEY`
- POST requests require the header: `Content-Type: application/json`

## Quick Start Workflow

1. **Spawn a bot:** `POST $MINECLAW_API_URL/api/bots` with body `{ "username": "Builder_1" }`
2. **Observe the world:** `GET $MINECLAW_API_URL/api/bots/{id}/observe`
3. **Execute tools:** `POST $MINECLAW_API_URL/api/bots/{id}/execute` with body `{ "tool": "fly_to", "input": { "x": 0, "y": -56, "z": 0 } }`
4. **Build structures:** `POST $MINECLAW_API_URL/api/bots/{id}/build/fill-batch` with body `{ "commands": [...] }`

Always follow this loop: **spawn → observe → plan → execute/build → observe → repeat** until the task is complete.

## API Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/auth/me | Get current user info. Returns `{ "username": "...", "token_valid": true }` |

### Bots

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | /api/bots | `{ "username": "Builder_1" }` | Spawn a new bot. Returns `{ "id": "...", "username": "Builder_1", "status": "idle" }` |
| GET | /api/bots | — | List all active bots. Returns array of `{ id, username, status, position }` |
| GET | /api/bots/{id} | — | Get full bot state (position, status, inventory) |
| DELETE | /api/bots/{id} | — | Despawn and remove a bot |

### Tool Execution

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | /api/bots/{id}/execute | `{ "tool": "navigate_to", "input": { "x": 10, "y": -60, "z": 20 } }` | Execute a single tool call on the bot. Returns `{ "success": true, "result": {...}, "bot_state": {...} }` |
| POST | /api/bots/{id}/execute-batch | `{ "tools": [ { "tool": "...", "input": {...} }, ... ] }` | Execute multiple tool calls in sequence |
| GET | /api/bots/{id}/observe | — | Get full world observation: position, inventory, nearby blocks, entities, time, weather |

### Creative Building (RCON-based)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | /api/bots/{id}/build/setblock | `{ "x": 0, "y": -60, "z": 0, "block": "minecraft:stone_bricks" }` | Place a single block |
| POST | /api/bots/{id}/build/fill | `{ "x1": 0, "y1": -60, "z1": 0, "x2": 10, "y2": -60, "z2": 10, "block": "minecraft:stone_bricks" }` | Fill a rectangular region with a block type |
| POST | /api/bots/{id}/build/fill-batch | `{ "commands": [ { "x1": 0, "y1": -60, "z1": 0, "x2": 10, "y2": -60, "z2": 10, "block": "minecraft:stone_bricks" }, ... ] }` | Execute multiple fill commands at once (best for structures) |

### Status

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/status | Server status: `{ "server_online": true, "address": "...", "bots_active": 2, "world_mode": "creative" }` |

## Available Bot Tools

Use these with `POST /api/bots/{id}/execute`:

| Tool | Parameters | Description |
|------|-----------|-------------|
| navigate_to | `x` (number), `y` (number), `z` (number), `range` (number, optional) | Walk to coordinates using A* pathfinding. `range` is how close to get (default 1). |
| fly_to | `x` (number), `y` (number), `z` (number) | Creative flight to coordinates. |
| teleport | `x` (number), `y` (number), `z` (number) | Instant teleport to coordinates. |
| navigate_to_player | `player_name` (string), `range` (number, optional) | Walk to a player by name. |
| look_around | *(none)* | Get a text description of surroundings (blocks, entities, structures nearby). |
| get_position | *(none)* | Get current bot coordinates `{ x, y, z }`. |
| check_inventory | *(none)* | List all items in the bot's inventory. |
| scan_nearby_blocks | `block_type` (string), `max_distance` (number, optional), `max_count` (number, optional) | Find specific blocks nearby. Returns array of coordinates. |
| place_block | `x` (number), `y` (number), `z` (number), `block_name` (string) | Place a block from inventory at coordinates. |
| give_item | `item` (string), `count` (number, optional) | Give the bot items from creative inventory (e.g., `"minecraft:diamond_sword"`). |
| chat | `message` (string) | Send a chat message in-game. |
| wait | `seconds` (number) | Idle for a specified time. |
| collect_nearby_items | `max_distance` (number, optional) | Pick up dropped items near the bot. |
| equip_item | `item_name` (string), `slot` (string, optional) | Equip an item to the bot's hand. |

## Building Strategy

For building structures, use `POST /api/bots/{id}/build/fill-batch`. This is much faster than placing blocks one at a time.

**How to build:**

1. **Break the structure into rectangular regions** — walls, floors, roofs, pillars, windows, doors are all rectangles.
2. **Use the `minecraft:` prefix** for all block names (e.g., `minecraft:stone_bricks`, `minecraft:oak_planks`).
3. **Fill exterior first, then carve interior with `minecraft:air`** — this is the easiest way to make hollow rooms.
4. **Add details last** — windows (glass), doors (air openings), interior features.

**Common blocks:**
- Walls: `minecraft:stone_bricks`, `minecraft:cobblestone`, `minecraft:oak_planks`, `minecraft:brick_block`
- Floors: `minecraft:stone_bricks`, `minecraft:oak_planks`, `minecraft:smooth_stone`
- Roofs: `minecraft:oak_planks`, `minecraft:oak_stairs`, `minecraft:dark_oak_planks`
- Windows: `minecraft:glass`, `minecraft:glass_pane`
- Doors: Use `minecraft:air` to create openings
- Lighting: `minecraft:glowstone`, `minecraft:lantern`, `minecraft:torch`
- Decoration: `minecraft:bookshelf`, `minecraft:crafting_table`, `minecraft:flower_pot`

## Building Example

Here is a complete fill-batch request that builds a simple 10x8x6 house at position (0, -60, 0):

```json
{
  "commands": [
    { "x1": 0, "y1": -60, "z1": 0, "x2": 10, "y2": -60, "z2": 8, "block": "minecraft:stone_bricks" },

    { "x1": 0, "y1": -59, "z1": 0, "x2": 10, "y2": -55, "z2": 8, "block": "minecraft:oak_planks" },

    { "x1": 1, "y1": -59, "z1": 1, "x2": 9, "y2": -55, "z2": 7, "block": "minecraft:air" },

    { "x1": 0, "y1": -54, "z1": 0, "x2": 10, "y2": -54, "z2": 8, "block": "minecraft:oak_planks" },

    { "x1": 3, "y1": -58, "z1": 0, "x2": 5, "y2": -57, "z2": 0, "block": "minecraft:glass" },
    { "x1": 3, "y1": -58, "z1": 8, "x2": 5, "y2": -57, "z2": 8, "block": "minecraft:glass" },
    { "x1": 0, "y1": -58, "z1": 3, "x2": 0, "y2": -57, "z2": 5, "block": "minecraft:glass" },
    { "x1": 10, "y1": -58, "z1": 3, "x2": 10, "y2": -57, "z2": 5, "block": "minecraft:glass" },

    { "x1": 5, "y1": -59, "z1": 0, "x2": 5, "y2": -58, "z2": 0, "block": "minecraft:air" }
  ]
}
```

This creates:
1. Stone brick floor (Y=-60)
2. Oak plank walls (Y=-59 to Y=-55) — fill solid, then carve interior with air
3. Oak plank roof (Y=-54)
4. Glass windows on all four walls
5. Door opening on the front wall

## Tips

- **Always observe before acting** — call `/observe` to understand the bot's surroundings, position, and inventory before planning actions.
- **Use fill-batch for structures** — it's much faster than placing blocks individually. Send all fill commands for a structure in one request.
- **Report progress to the user** after milestones (e.g., "Foundation laid", "Walls built", "Roof complete").
- **Bot has creative mode** — unlimited blocks, can fly, no health concerns.
- **Coordinate system:** X = east(+)/west(−), Y = up(+)/down(−), Z = south(+)/north(−).
- **Y=-60 is ground level** on a flat world. Build upward from there.
- **Use `get_position` or `observe`** to find the bot's current location before building nearby.
- **For complex builds**, break them into phases: foundation → walls → roof → interior → details.
- **Block names** always use the `minecraft:` prefix (e.g., `minecraft:stone_bricks`, not just `stone_bricks`).
