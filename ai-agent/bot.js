const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const express = require('express')

const BOT_USERNAME = 'ClaudeBot'
const MC_HOST = 'localhost'
const MC_PORT = 25565
const API_PORT = 3001

let bot = null
let currentTask = null
let botReady = false

function createBot() {
  if (bot) {
    try { bot.quit() } catch (e) {}
  }

  console.log(`[Bot] Connecting as ${BOT_USERNAME} to ${MC_HOST}:${MC_PORT}...`)

  bot = mineflayer.createBot({
    host: MC_HOST,
    port: MC_PORT,
    username: BOT_USERNAME,
    auth: 'offline',
    version: false,
    hideErrors: false,
  })

  bot.loadPlugin(pathfinder)

  bot.once('spawn', () => {
    console.log('[Bot] Spawned in world!')
    botReady = true

    const defaultMove = new Movements(bot)
    defaultMove.canDig = true
    defaultMove.allow1by1towers = true
    defaultMove.canOpenDoors = true
    defaultMove.allowFreeMotion = false
    defaultMove.allowParkour = true
    bot.pathfinder.setMovements(defaultMove)
  })

  bot.on('error', (err) => {
    console.log('[Bot] Error:', err.message)
  })

  bot.on('kicked', (reason) => {
    console.log('[Bot] Kicked:', reason)
    botReady = false
    setTimeout(createBot, 10000)
  })

  bot.on('end', () => {
    console.log('[Bot] Disconnected')
    botReady = false
    setTimeout(createBot, 10000)
  })

  bot.on('death', () => {
    console.log('[Bot] Died, respawning...')
    bot.respawn && bot.respawn()
  })
}

function getToolDefinitions() {
  return [
    {
      name: "navigate_to",
      description: "Walk to a specific position using A* pathfinding. The bot will find a path around obstacles, jump over gaps, and break blocks if needed.",
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
      name: "mine_block",
      description: "Mine/break a specific block at the given coordinates. Bot must be close enough to reach it (within 4 blocks). The bot will equip the best tool automatically.",
      input_schema: {
        type: "object",
        properties: {
          x: { type: "integer", description: "X coordinate of block" },
          y: { type: "integer", description: "Y coordinate of block" },
          z: { type: "integer", description: "Z coordinate of block" }
        },
        required: ["x", "y", "z"]
      }
    },
    {
      name: "mine_type",
      description: "Find and mine a number of blocks of the specified type. Bot will pathfind to each block and mine it.",
      input_schema: {
        type: "object",
        properties: {
          block_type: { type: "string", description: "Block name like 'oak_log', 'stone', 'diamond_ore'" },
          count: { type: "integer", description: "How many to mine (default 1)", default: 1 },
          max_distance: { type: "integer", description: "Max search distance (default 64)", default: 64 }
        },
        required: ["block_type"]
      }
    },
    {
      name: "place_block",
      description: "Place a block from inventory at the specified position. Must be close enough and have the block in inventory.",
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
      name: "craft_item",
      description: "Craft an item using available materials in inventory. If a crafting table is needed and one isn't nearby, will report that.",
      input_schema: {
        type: "object",
        properties: {
          item_name: { type: "string", description: "Name of item to craft like 'oak_planks', 'stick', 'crafting_table'" },
          count: { type: "integer", description: "How many to craft (default 1)", default: 1 }
        },
        required: ["item_name"]
      }
    },
    {
      name: "check_inventory",
      description: "Check the bot's current inventory contents.",
      input_schema: { type: "object", properties: {} }
    },
    {
      name: "drop_item",
      description: "Drop items from inventory on the ground.",
      input_schema: {
        type: "object",
        properties: {
          item_name: { type: "string", description: "Name of item to drop" },
          count: { type: "integer", description: "How many to drop (default all)", default: -1 }
        },
        required: ["item_name"]
      }
    },
    {
      name: "toss_to_player",
      description: "Toss/throw items to a nearby player. Bot must be close to the player.",
      input_schema: {
        type: "object",
        properties: {
          player_name: { type: "string", description: "Player to toss items to" },
          item_name: { type: "string", description: "Name of item to toss" },
          count: { type: "integer", description: "How many to toss (default all)", default: -1 }
        },
        required: ["player_name", "item_name"]
      }
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
      description: "Wait for a specified number of seconds. Useful for waiting for items to drop or for other processes.",
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
      name: "attack_entity",
      description: "Attack the nearest entity of a given type.",
      input_schema: {
        type: "object",
        properties: {
          entity_type: { type: "string", description: "Entity type like 'cow', 'pig', 'zombie', 'chicken'" }
        },
        required: ["entity_type"]
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
      name: "task_complete",
      description: "Call this when the assigned task has been completed successfully. Describe what was accomplished.",
      input_schema: {
        type: "object",
        properties: {
          summary: { type: "string", description: "Brief summary of what was accomplished" }
        },
        required: ["summary"]
      }
    },
    {
      name: "task_failed",
      description: "Call this when the task cannot be completed. Explain why.",
      input_schema: {
        type: "object",
        properties: {
          reason: { type: "string", description: "Why the task failed" }
        },
        required: ["reason"]
      }
    }
  ]
}

async function executeTool(toolName, toolInput) {
  if (!bot || !botReady) {
    return { error: "Bot is not connected to the server" }
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

      case "mine_block": {
        const { x, y, z } = toolInput
        const block = bot.blockAt(bot.vec3(x, y, z))
        if (!block || block.name === 'air') {
          return { error: `No block at (${x}, ${y}, ${z})` }
        }
        const tool = bot.pathfinder.bestHarvestTool(block)
        if (tool) await bot.equip(tool, 'hand')
        await bot.dig(block)
        return { success: true, message: `Mined ${block.name} at (${x}, ${y}, ${z})` }
      }

      case "mine_type": {
        const { block_type, count = 1, max_distance = 64 } = toolInput
        const blockId = bot.registry.blocksByName[block_type]
        if (!blockId) {
          return { error: `Unknown block type: ${block_type}` }
        }

        let mined = 0
        for (let i = 0; i < count; i++) {
          const block = bot.findBlock({
            matching: blockId.id,
            maxDistance: max_distance
          })
          if (!block) {
            return { success: mined > 0, message: `Mined ${mined}/${count} ${block_type} (no more found within ${max_distance} blocks)` }
          }

          await bot.pathfinder.goto(new goals.GoalBlock(block.position.x, block.position.y, block.position.z))

          const targetBlock = bot.blockAt(block.position)
          if (targetBlock && targetBlock.name !== 'air') {
            const tool = bot.pathfinder.bestHarvestTool(targetBlock)
            if (tool) await bot.equip(tool, 'hand')
            await bot.dig(targetBlock)
            mined++
          }
        }
        return { success: true, message: `Mined ${mined} ${block_type}` }
      }

      case "place_block": {
        const { x, y, z, block_name } = toolInput
        const item = bot.inventory.items().find(i => i.name === block_name)
        if (!item) {
          return { error: `${block_name} not in inventory` }
        }
        await bot.equip(item, 'hand')
        const refBlock = bot.blockAt(bot.vec3(x, y - 1, z))
        if (!refBlock) {
          return { error: `No reference block below (${x}, ${y}, ${z})` }
        }
        await bot.placeBlock(refBlock, bot.vec3(0, 1, 0))
        return { success: true, message: `Placed ${block_name} at (${x}, ${y}, ${z})` }
      }

      case "craft_item": {
        const { item_name, count = 1 } = toolInput
        const item = bot.registry.itemsByName[item_name]
        if (!item) {
          return { error: `Unknown item: ${item_name}` }
        }

        const craftingTable = bot.findBlock({
          matching: bot.registry.blocksByName.crafting_table?.id,
          maxDistance: 32
        })

        const recipes = bot.recipesFor(item.id, null, 1, craftingTable)
        if (recipes.length === 0) {
          const recipesNoTable = bot.recipesFor(item.id, null, 1, null)
          if (recipesNoTable.length > 0) {
            await bot.craft(recipesNoTable[0], count, null)
            return { success: true, message: `Crafted ${count}x ${item_name} (from inventory)` }
          }
          return { error: `No recipe found for ${item_name}. Make sure you have the required materials. ${craftingTable ? '' : 'No crafting table nearby - some recipes require one.'}` }
        }

        if (craftingTable) {
          const dist = bot.entity.position.distanceTo(craftingTable.position)
          if (dist > 4) {
            await bot.pathfinder.goto(new goals.GoalNear(craftingTable.position.x, craftingTable.position.y, craftingTable.position.z, 2))
          }
        }

        await bot.craft(recipes[0], count, craftingTable)
        return { success: true, message: `Crafted ${count}x ${item_name}` }
      }

      case "check_inventory": {
        const items = bot.inventory.items()
        if (items.length === 0) {
          return { inventory: [], message: "Inventory is empty" }
        }
        const itemList = items.map(i => ({ name: i.name, count: i.count, slot: i.slot }))
        return { inventory: itemList, message: `${items.length} item stacks in inventory` }
      }

      case "drop_item": {
        const { item_name, count = -1 } = toolInput
        const item = bot.inventory.items().find(i => i.name === item_name)
        if (!item) {
          return { error: `${item_name} not in inventory` }
        }
        const dropCount = count === -1 ? item.count : Math.min(count, item.count)
        await bot.tossStack(item)
        return { success: true, message: `Dropped ${dropCount}x ${item_name}` }
      }

      case "toss_to_player": {
        const { player_name, item_name, count = -1 } = toolInput
        const player = bot.players[player_name]
        if (!player || !player.entity) {
          return { error: `Player ${player_name} not found or not visible` }
        }
        const dist = bot.entity.position.distanceTo(player.entity.position)
        if (dist > 5) {
          await bot.pathfinder.goto(new goals.GoalNear(player.entity.position.x, player.entity.position.y, player.entity.position.z, 2))
        }
        await bot.lookAt(player.entity.position.offset(0, 1.6, 0))
        const item = bot.inventory.items().find(i => i.name === item_name)
        if (!item) {
          return { error: `${item_name} not in inventory` }
        }
        const tossCount = count === -1 ? item.count : Math.min(count, item.count)
        await bot.toss(item.type, null, tossCount)
        return { success: true, message: `Tossed ${tossCount}x ${item_name} to ${player_name}` }
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
        const biome = bot.blockAt(bot.entity.position)

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

      case "attack_entity": {
        const { entity_type } = toolInput
        const entity = bot.nearestEntity(e =>
          e.name === entity_type && bot.entity.position.distanceTo(e.position) < 32
        )
        if (!entity) {
          return { error: `No ${entity_type} found nearby` }
        }
        await bot.pathfinder.goto(new goals.GoalNear(entity.position.x, entity.position.y, entity.position.z, 2))
        bot.attack(entity)
        return { success: true, message: `Attacked ${entity_type}` }
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

      case "task_complete": {
        return { task_done: true, status: "complete", summary: toolInput.summary }
      }

      case "task_failed": {
        return { task_done: true, status: "failed", reason: toolInput.reason }
      }

      default:
        return { error: `Unknown tool: ${toolName}` }
    }
  } catch (err) {
    return { error: err.message }
  }
}

const app = express()
app.use(express.json())

app.get('/status', (req, res) => {
  res.json({
    connected: botReady,
    username: BOT_USERNAME,
    position: botReady ? {
      x: Math.round(bot.entity.position.x),
      y: Math.round(bot.entity.position.y),
      z: Math.round(bot.entity.position.z)
    } : null,
    health: botReady ? bot.health : null,
    busy: currentTask !== null,
    currentTask: currentTask
  })
})

app.get('/tools', (req, res) => {
  res.json(getToolDefinitions())
})

app.post('/execute', async (req, res) => {
  const { tool, input } = req.body
  if (!tool) {
    return res.status(400).json({ error: "Missing 'tool' field" })
  }
  try {
    const result = await executeTool(tool, input || {})
    res.json(result)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.post('/task', (req, res) => {
  const { task, player_name } = req.body
  if (!task) {
    return res.status(400).json({ error: "Missing 'task' field" })
  }
  if (currentTask) {
    return res.status(409).json({ error: "Bot is already working on a task", currentTask })
  }
  currentTask = { task, player_name, started: Date.now() }
  res.json({ accepted: true, message: `Task accepted: ${task}` })
})

app.post('/task/clear', (req, res) => {
  currentTask = null
  res.json({ success: true })
})

app.get('/task', (req, res) => {
  res.json({ currentTask })
})

function waitForServer() {
  const net = require('net')
  const check = () => {
    const sock = new net.Socket()
    sock.setTimeout(2000)
    sock.on('connect', () => {
      sock.destroy()
      console.log('[Bot] Minecraft server is ready, connecting...')
      setTimeout(createBot, 2000)
    })
    sock.on('error', () => {
      sock.destroy()
      setTimeout(check, 3000)
    })
    sock.on('timeout', () => {
      sock.destroy()
      setTimeout(check, 3000)
    })
    sock.connect(MC_PORT, MC_HOST)
  }
  check()
}

app.listen(API_PORT, '127.0.0.1', () => {
  console.log(`[Bot] HTTP API listening on port ${API_PORT}`)
  waitForServer()
})

module.exports = { executeTool, getToolDefinitions }
