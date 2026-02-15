const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')
const express = require('express')
const crypto = require('crypto')
const net = require('net')
const https = require('https')
const http = require('http')

const MC_HOST = 'localhost'
const MC_PORT = 25565
const API_PORT = 3001

const bots = new Map()
let serverAvailable = false

function checkServerAvailable() {
  return new Promise((resolve) => {
    const sock = new net.Socket()
    sock.setTimeout(2000)
    sock.on('connect', () => {
      sock.destroy()
      resolve(true)
    })
    sock.on('error', () => {
      sock.destroy()
      resolve(false)
    })
    sock.on('timeout', () => {
      sock.destroy()
      resolve(false)
    })
    sock.connect(MC_PORT, MC_HOST)
  })
}

function pollServer() {
  const check = async () => {
    const available = await checkServerAvailable()
    if (available && !serverAvailable) {
      console.log('[BotManager] Minecraft server is available')
    }
    serverAvailable = available
    setTimeout(check, 5000)
  }
  check()
}

function getBotState(botId) {
  const entry = bots.get(botId)
  if (!entry) return null
  const { bot, username, status, ready } = entry
  const pos = ready && bot.entity ? {
    x: Math.round(bot.entity.position.x),
    y: Math.round(bot.entity.position.y),
    z: Math.round(bot.entity.position.z)
  } : null
  return { id: botId, username, status, position: pos }
}

function getFullBotState(botId) {
  const entry = bots.get(botId)
  if (!entry) return null
  const { bot, username, status, ready } = entry
  const pos = ready && bot.entity ? {
    x: Math.round(bot.entity.position.x),
    y: Math.round(bot.entity.position.y),
    z: Math.round(bot.entity.position.z)
  } : null
  return {
    id: botId,
    username,
    status,
    position: pos,
    health: ready ? bot.health : null,
    food: ready ? bot.food : null
  }
}

function getToolDefinitions() {
  return [
    {
      name: "navigate_to",
      description: "Walk to a specific position using A* pathfinding.",
      input_schema: {
        type: "object",
        properties: {
          x: { type: "number", description: "X coordinate" },
          y: { type: "number", description: "Y coordinate" },
          z: { type: "number", description: "Z coordinate" },
          range: { type: "number", description: "How close to get (default 1)", default: 1 }
        },
        required: ["x", "y", "z"]
      }
    },
    {
      name: "navigate_to_player",
      description: "Walk to a specific player's current position.",
      input_schema: {
        type: "object",
        properties: {
          player_name: { type: "string", description: "The player's username" },
          range: { type: "number", description: "How close to get (default 2)", default: 2 }
        },
        required: ["player_name"]
      }
    },
    {
      name: "look_around",
      description: "Get a description of the bot's surroundings: nearby blocks, entities, players, and position.",
      input_schema: { type: "object", properties: {} }
    },
    {
      name: "get_position",
      description: "Get the bot's current position coordinates.",
      input_schema: { type: "object", properties: {} }
    },
    {
      name: "check_inventory",
      description: "Check the bot's current inventory contents.",
      input_schema: { type: "object", properties: {} }
    },
    {
      name: "scan_nearby_blocks",
      description: "Scan the area around the bot for specific block types. Returns positions of matching blocks.",
      input_schema: {
        type: "object",
        properties: {
          block_type: { type: "string", description: "Block name to search for like 'oak_log', 'crafting_table', 'diamond_ore'" },
          max_distance: { type: "integer", description: "Max search distance (default 32)", default: 32 },
          max_count: { type: "integer", description: "Max blocks to return (default 10)", default: 10 }
        },
        required: ["block_type"]
      }
    },
    {
      name: "place_block",
      description: "Place a block from inventory at the specified position.",
      input_schema: {
        type: "object",
        properties: {
          x: { type: "integer", description: "X coordinate to place at" },
          y: { type: "integer", description: "Y coordinate to place at" },
          z: { type: "integer", description: "Z coordinate to place at" },
          block_name: { type: "string", description: "Name of the block to place (must be in inventory)" }
        },
        required: ["x", "y", "z", "block_name"]
      }
    },
    {
      name: "chat",
      description: "Send a chat message in-game.",
      input_schema: {
        type: "object",
        properties: {
          message: { type: "string", description: "Message to send" }
        },
        required: ["message"]
      }
    },
    {
      name: "wait",
      description: "Wait for a specified number of seconds (max 30).",
      input_schema: {
        type: "object",
        properties: {
          seconds: { type: "number", description: "Seconds to wait (max 30)", default: 2 }
        },
        required: ["seconds"]
      }
    },
    {
      name: "collect_nearby_items",
      description: "Walk around and pick up dropped items near the bot.",
      input_schema: {
        type: "object",
        properties: {
          max_distance: { type: "number", description: "Max distance to search (default 16)", default: 16 }
        }
      }
    },
    {
      name: "equip_item",
      description: "Equip an item from inventory to hand, head, torso, legs, or feet.",
      input_schema: {
        type: "object",
        properties: {
          item_name: { type: "string", description: "Item name to equip" },
          slot: { type: "string", description: "Where to equip: 'hand', 'off-hand', 'head', 'torso', 'legs', 'feet'", default: "hand" }
        },
        required: ["item_name"]
      }
    },
    {
      name: "fly_to",
      description: "Fly to a specific position using creative mode flight.",
      input_schema: {
        type: "object",
        properties: {
          x: { type: "number", description: "X coordinate" },
          y: { type: "number", description: "Y coordinate" },
          z: { type: "number", description: "Z coordinate" }
        },
        required: ["x", "y", "z"]
      }
    },
    {
      name: "teleport",
      description: "Instantly teleport to a position using /tp command.",
      input_schema: {
        type: "object",
        properties: {
          x: { type: "number", description: "X coordinate" },
          y: { type: "number", description: "Y coordinate" },
          z: { type: "number", description: "Z coordinate" }
        },
        required: ["x", "y", "z"]
      }
    },
    {
      name: "give_item",
      description: "Give items to the bot using /give command (creative/op).",
      input_schema: {
        type: "object",
        properties: {
          item: { type: "string", description: "Item name like 'diamond', 'stone', 'oak_planks'" },
          count: { type: "integer", description: "Number of items (default 1)", default: 1 }
        },
        required: ["item"]
      }
    }
  ]
}

async function executeTool(botId, toolName, toolInput) {
  const entry = bots.get(botId)
  if (!entry) {
    return { error: "Bot not found" }
  }
  const { bot, ready } = entry
  if (!bot || !ready) {
    return { error: "Bot is not ready" }
  }

  try {
    switch (toolName) {
      case "navigate_to": {
        const { x, y, z, range = 1 } = toolInput
        const goal = new goals.GoalNear(x, y, z, range)
        await bot.pathfinder.goto(goal)
        const pos = bot.entity.position
        return { success: true, message: `Arrived at (${Math.round(pos.x)}, ${Math.round(pos.y)}, ${Math.round(pos.z)})` }
      }

      case "navigate_to_player": {
        const { player_name, range = 2 } = toolInput
        const player = bot.players[player_name]
        if (!player || !player.entity) {
          return { error: `Player ${player_name} not found or not visible` }
        }
        const p = player.entity.position
        await bot.pathfinder.goto(new goals.GoalNear(p.x, p.y, p.z, range))
        return { success: true, message: `Arrived near ${player_name}` }
      }

      case "look_around": {
        const pos = bot.entity.position
        const nearbyPlayers = Object.values(bot.players)
          .filter(p => p.entity && p.username !== bot.username)
          .map(p => ({
            name: p.username,
            distance: Math.round(bot.entity.position.distanceTo(p.entity.position)),
            position: { x: Math.round(p.entity.position.x), y: Math.round(p.entity.position.y), z: Math.round(p.entity.position.z) }
          }))

        const nearbyEntities = Object.values(bot.entities)
          .filter(e => e !== bot.entity && e.type !== 'player' && bot.entity.position.distanceTo(e.position) < 32)
          .slice(0, 15)
          .map(e => ({
            type: e.name || e.type,
            distance: Math.round(bot.entity.position.distanceTo(e.position)),
            position: { x: Math.round(e.position.x), y: Math.round(e.position.y), z: Math.round(e.position.z) }
          }))

        const blockBelow = bot.blockAt(bot.entity.position.offset(0, -1, 0))

        return {
          bot_position: { x: Math.round(pos.x), y: Math.round(pos.y), z: Math.round(pos.z) },
          health: bot.health,
          food: bot.food,
          time_of_day: bot.time.timeOfDay,
          block_below: blockBelow?.name || "unknown",
          nearby_players: nearbyPlayers,
          nearby_entities: nearbyEntities,
        }
      }

      case "get_position": {
        const pos = bot.entity.position
        return { x: Math.round(pos.x), y: Math.round(pos.y), z: Math.round(pos.z) }
      }

      case "check_inventory": {
        const items = bot.inventory.items()
        if (items.length === 0) {
          return { inventory: [], message: "Inventory is empty" }
        }
        const itemList = items.map(i => ({ name: i.name, count: i.count, slot: i.slot }))
        return { inventory: itemList, message: `${items.length} item stacks in inventory` }
      }

      case "scan_nearby_blocks": {
        const { block_type, max_distance = 32, max_count = 10 } = toolInput
        const blockId = bot.registry.blocksByName[block_type]
        if (!blockId) {
          return { error: `Unknown block type: ${block_type}` }
        }
        const blocks = bot.findBlocks({
          matching: blockId.id,
          maxDistance: max_distance,
          count: max_count
        })
        const positions = blocks.map(pos => ({ x: pos.x, y: pos.y, z: pos.z }))
        return { blocks: positions, count: positions.length, message: `Found ${positions.length} ${block_type} within ${max_distance} blocks` }
      }

      case "place_block": {
        const { x, y, z, block_name } = toolInput
        const item = bot.inventory.items().find(i => i.name === block_name)
        if (!item) {
          return { error: `${block_name} not in inventory` }
        }
        await bot.equip(item, 'hand')
        const refBlock = bot.blockAt(new Vec3(x, y - 1, z))
        if (!refBlock) {
          return { error: `No reference block below (${x}, ${y}, ${z})` }
        }
        await bot.placeBlock(refBlock, new Vec3(0, 1, 0))
        return { success: true, message: `Placed ${block_name} at (${x}, ${y}, ${z})` }
      }

      case "chat": {
        const { message } = toolInput
        bot.chat(message)
        return { success: true, message: `Sent: ${message}` }
      }

      case "wait": {
        const { seconds } = toolInput
        const waitTime = Math.min(seconds, 30) * 1000
        await new Promise(resolve => setTimeout(resolve, waitTime))
        return { success: true, message: `Waited ${Math.min(seconds, 30)} seconds` }
      }

      case "collect_nearby_items": {
        const { max_distance = 16 } = toolInput
        const items = Object.values(bot.entities).filter(e =>
          e.type === 'object' && e.objectType === 'Item' &&
          bot.entity.position.distanceTo(e.position) < max_distance
        )
        if (items.length === 0) {
          return { message: "No dropped items nearby" }
        }
        let collected = 0
        for (const item of items.slice(0, 10)) {
          try {
            await bot.pathfinder.goto(new goals.GoalNear(item.position.x, item.position.y, item.position.z, 0))
            collected++
            await new Promise(r => setTimeout(r, 300))
          } catch (e) {}
        }
        return { success: true, message: `Collected ${collected} item(s)` }
      }

      case "equip_item": {
        const { item_name, slot = "hand" } = toolInput
        const item = bot.inventory.items().find(i => i.name === item_name)
        if (!item) {
          return { error: `${item_name} not in inventory` }
        }
        await bot.equip(item, slot)
        return { success: true, message: `Equipped ${item_name} to ${slot}` }
      }

      case "fly_to": {
        const { x, y, z } = toolInput
        await bot.creative.flyTo(new Vec3(x, y, z))
        return { success: true, message: `Flew to (${x}, ${y}, ${z})` }
      }

      case "teleport": {
        const { x, y, z } = toolInput
        bot.chat(`/tp ${bot.username} ${x} ${y} ${z}`)
        await new Promise(resolve => setTimeout(resolve, 500))
        return { success: true, message: `Teleported to (${x}, ${y}, ${z})` }
      }

      case "give_item": {
        const { item, count = 1 } = toolInput
        bot.chat(`/give ${bot.username} ${item} ${count}`)
        await new Promise(resolve => setTimeout(resolve, 500))
        return { success: true, message: `Gave ${count}x ${item}` }
      }

      default:
        return { error: `Unknown tool: ${toolName}` }
    }
  } catch (err) {
    return { error: err.message }
  }
}

function getObservation(botId) {
  const entry = bots.get(botId)
  if (!entry) return null
  const { bot, ready } = entry
  if (!bot || !ready) return null

  const pos = bot.entity.position

  const inventory = bot.inventory.items().map(i => ({ name: i.name, count: i.count, slot: i.slot }))

  const commonBlockTypes = [
    'stone', 'dirt', 'grass_block', 'sand', 'gravel',
    'oak_log', 'spruce_log', 'birch_log', 'jungle_log', 'acacia_log', 'dark_oak_log',
    'oak_planks', 'spruce_planks', 'birch_planks',
    'oak_leaves', 'spruce_leaves', 'birch_leaves',
    'water', 'lava',
    'coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore', 'emerald_ore',
    'crafting_table', 'furnace', 'chest',
    'cobblestone', 'glass', 'brick',
  ]

  const nearbyBlocks = {}
  for (const blockType of commonBlockTypes) {
    const blockDef = bot.registry.blocksByName[blockType]
    if (!blockDef) continue
    const found = bot.findBlocks({
      matching: blockDef.id,
      maxDistance: 16,
      count: 100
    })
    if (found.length > 0) {
      nearbyBlocks[blockType] = found.length
    }
  }

  const nearbyEntities = Object.values(bot.entities)
    .filter(e => e !== bot.entity && e.type !== 'player' && bot.entity.position.distanceTo(e.position) < 32)
    .slice(0, 20)
    .map(e => ({
      type: e.name || e.type,
      distance: Math.round(bot.entity.position.distanceTo(e.position)),
      position: { x: Math.round(e.position.x), y: Math.round(e.position.y), z: Math.round(e.position.z) }
    }))

  const nearbyPlayers = Object.values(bot.players)
    .filter(p => p.entity && p.username !== bot.username)
    .map(p => ({
      name: p.username,
      distance: Math.round(bot.entity.position.distanceTo(p.entity.position)),
      position: { x: Math.round(p.entity.position.x), y: Math.round(p.entity.position.y), z: Math.round(p.entity.position.z) }
    }))

  return {
    position: { x: Math.round(pos.x), y: Math.round(pos.y), z: Math.round(pos.z) },
    health: bot.health,
    food: bot.food,
    inventory,
    nearby_blocks: nearbyBlocks,
    nearby_entities: nearbyEntities,
    nearby_players: nearbyPlayers,
    time_of_day: bot.time.timeOfDay,
    weather: bot.isRaining ? 'rain' : 'clear'
  }
}

const app = express()
app.use(express.json())

app.post('/spawn', async (req, res) => {
  try {
    if (!serverAvailable) {
      return res.status(503).json({ error: "Minecraft server is not available yet" })
    }

    const { username } = req.body
    if (!username) {
      return res.status(400).json({ error: "Missing 'username' field" })
    }

    const botId = crypto.randomUUID()

    const bot = mineflayer.createBot({
      host: MC_HOST,
      port: MC_PORT,
      username: username,
      auth: 'offline',
      version: false,
      hideErrors: false,
    })

    const entry = { bot, username, status: 'spawning', ready: false, movements: null }
    bots.set(botId, entry)

    bot.loadPlugin(pathfinder)

    bot.once('spawn', () => {
      console.log(`[BotManager] Bot ${username} (${botId}) spawned`)
      const movements = new Movements(bot)
      movements.canDig = true
      movements.allow1by1towers = true
      movements.canOpenDoors = true
      movements.allowFreeMotion = false
      movements.allowParkour = true
      bot.pathfinder.setMovements(movements)
      entry.movements = movements
      entry.status = 'ready'
      entry.ready = true

      bot.on('chat', (chatUsername, chatMessage) => {
        const botUsernames = new Set()
        for (const [, e] of bots) {
          botUsernames.add(e.username)
        }
        if (botUsernames.has(chatUsername)) return
        if (!chatMessage.startsWith('!ai ')) return

        const aiMessage = chatMessage.slice(4)
        const webhookUrl = process.env.OPENCLAW_WEBHOOK_URL
        const webhookToken = process.env.OPENCLAW_WEBHOOK_TOKEN

        if (!webhookUrl || !webhookToken) {
          console.log('[ChatBridge] OPENCLAW_WEBHOOK_URL or OPENCLAW_WEBHOOK_TOKEN not set, skipping forwarding')
          return
        }

        let position = null
        try {
          const player = bot.players[chatUsername]
          if (player && player.entity && player.entity.position) {
            position = {
              x: Math.round(player.entity.position.x),
              y: Math.round(player.entity.position.y),
              z: Math.round(player.entity.position.z)
            }
          }
        } catch (e) {}

        const payload = JSON.stringify({
          player: chatUsername,
          message: aiMessage,
          position: position
        })

        console.log(`[ChatBridge] Forwarding message from ${chatUsername}: ${aiMessage}`)

        try {
          const urlObj = new URL(webhookUrl)
          const reqModule = urlObj.protocol === 'https:' ? https : http
          const reqOptions = {
            hostname: urlObj.hostname,
            port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
            path: urlObj.pathname + urlObj.search,
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${webhookToken}`,
              'Content-Length': Buffer.byteLength(payload)
            }
          }

          const req = reqModule.request(reqOptions, (res) => {
            let body = ''
            res.on('data', (chunk) => { body += chunk })
            res.on('end', () => {
              if (res.statusCode >= 200 && res.statusCode < 300) {
                console.log(`[ChatBridge] Webhook response: ${res.statusCode}`)
              } else {
                console.log(`[ChatBridge] Webhook error: ${res.statusCode} ${body}`)
              }
            })
          })

          req.on('error', (err) => {
            console.log(`[ChatBridge] Webhook request error: ${err.message}`)
          })

          req.write(payload)
          req.end()
        } catch (err) {
          console.log(`[ChatBridge] Failed to send webhook: ${err.message}`)
        }
      })
    })

    bot.on('error', (err) => {
      console.log(`[BotManager] Bot ${username} (${botId}) error:`, err.message)
    })

    bot.on('kicked', (reason) => {
      console.log(`[BotManager] Bot ${username} (${botId}) kicked:`, reason)
      entry.status = 'disconnected'
      entry.ready = false
    })

    bot.on('end', () => {
      console.log(`[BotManager] Bot ${username} (${botId}) disconnected`)
      entry.status = 'disconnected'
      entry.ready = false
    })

    bot.on('death', () => {
      console.log(`[BotManager] Bot ${username} (${botId}) died, respawning...`)
      bot.respawn && bot.respawn()
    })

    res.json({ id: botId, username, status: 'spawning' })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.delete('/despawn/:id', (req, res) => {
  try {
    const { id } = req.params
    const entry = bots.get(id)
    if (!entry) {
      return res.status(404).json({ error: "Bot not found" })
    }
    try { entry.bot.quit() } catch (e) {}
    bots.delete(id)
    console.log(`[BotManager] Bot ${entry.username} (${id}) despawned`)
    res.json({ success: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.get('/bots', (req, res) => {
  try {
    const list = []
    for (const [id] of bots) {
      list.push(getBotState(id))
    }
    res.json(list)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.get('/bots/:id', (req, res) => {
  try {
    const state = getFullBotState(req.params.id)
    if (!state) {
      return res.status(404).json({ error: "Bot not found" })
    }
    res.json(state)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.post('/bots/:id/execute', async (req, res) => {
  try {
    const { id } = req.params
    const { tool, input } = req.body
    if (!tool) {
      return res.status(400).json({ error: "Missing 'tool' field" })
    }
    const entry = bots.get(id)
    if (!entry) {
      return res.status(404).json({ error: "Bot not found" })
    }
    const result = await executeTool(id, tool, input || {})
    const botState = entry.ready && entry.bot.entity ? {
      position: {
        x: Math.round(entry.bot.entity.position.x),
        y: Math.round(entry.bot.entity.position.y),
        z: Math.round(entry.bot.entity.position.z)
      },
      health: entry.bot.health,
      food: entry.bot.food
    } : null
    res.json({ result, bot_state: botState })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.get('/bots/:id/observe', (req, res) => {
  try {
    const observation = getObservation(req.params.id)
    if (!observation) {
      const entry = bots.get(req.params.id)
      if (!entry) {
        return res.status(404).json({ error: "Bot not found" })
      }
      return res.status(503).json({ error: "Bot is not ready" })
    }
    res.json(observation)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.get('/bots/:id/tools', (req, res) => {
  try {
    const entry = bots.get(req.params.id)
    if (!entry) {
      return res.status(404).json({ error: "Bot not found" })
    }
    res.json(getToolDefinitions())
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.listen(API_PORT, '127.0.0.1', () => {
  console.log(`[BotManager] HTTP API listening on 127.0.0.1:${API_PORT}`)
  pollServer()
})
