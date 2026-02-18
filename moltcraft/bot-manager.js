const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')
const express = require('express')
const crypto = require('crypto')
const net = require('net')

const MC_HOST = 'localhost'
const MC_PORT = 25565
const API_PORT = 3001

const bots = new Map()
let serverAvailable = false

const MAX_CHAT_BUFFER = 200
const chatBuffer = []

function addChatMessage(sender, message) {
  if (!sender || !message) return
  if (message.startsWith('/')) return

  chatBuffer.push({
    sender,
    message,
    timestamp: new Date().toISOString()
  })

  while (chatBuffer.length > MAX_CHAT_BUFFER) {
    chatBuffer.shift()
  }
}

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

      case "chat": {
        let { message } = toolInput
        if (typeof message !== 'string' || message.length === 0) {
          return { error: "Message must be a non-empty string" }
        }
        message = message.substring(0, 500)
        if (message.startsWith('/')) {
          message = '.' + message
        }
        bot.chat(message)
        return { success: true, message: `Sent: ${message}` }
      }

      case "teleport": {
        const { x, y, z } = toolInput
        bot.chat(`/tp ${bot.username} ${x} ${y} ${z}`)
        await new Promise(resolve => setTimeout(resolve, 500))
        return { success: true, message: `Teleported to (${x}, ${y}, ${z})` }
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
    })

    bot.on('chat', (username, message) => {
      if (!username) return
      addChatMessage(username, message)
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

app.get('/chat', (req, res) => {
  try {
    const limit = Math.min(Math.max(parseInt(req.query.limit) || 20, 1), 200)
    const sorted = [...chatBuffer].reverse()
    const messages = sorted.slice(0, limit)
    res.json({ messages, total: chatBuffer.length })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.post('/bots/:id/walk-to', async (req, res) => {
  try {
    const { id } = req.params
    const entry = bots.get(id)
    if (!entry) {
      return res.status(404).json({ error: "Bot not found" })
    }
    const { bot, ready } = entry
    if (!bot || !ready) {
      return res.status(503).json({ error: "Bot is not ready" })
    }

    const { x, y, z, timeout = 10 } = req.body
    if (x == null || y == null || z == null) {
      return res.status(400).json({ error: "Missing x, y, or z coordinates" })
    }

    const dx = x - bot.entity.position.x
    const dz = z - bot.entity.position.z
    const dist = Math.sqrt(dx * dx + dz * dz)

    if (dist > 10) {
      const ratio = 10 / dist
      const nearX = Math.round(x - dx * ratio)
      const nearZ = Math.round(z - dz * ratio)
      bot.chat(`/tp ${bot.username} ${nearX} ${y} ${nearZ}`)
      await new Promise(resolve => setTimeout(resolve, 500))
    }

    const timeoutMs = Math.max(timeout, 1) * 1000
    let method = 'walked'

    try {
      const goal = new goals.GoalNear(x, y, z, 1)
      await Promise.race([
        bot.pathfinder.goto(goal),
        new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), timeoutMs))
      ])
    } catch (err) {
      try { bot.pathfinder.stop() } catch (e) {}
      bot.chat(`/tp ${bot.username} ${x} ${y} ${z}`)
      await new Promise(resolve => setTimeout(resolve, 500))
      method = 'teleported'
    }

    res.json({ success: true, method })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

app.listen(API_PORT, '127.0.0.1', () => {
  console.log(`[BotManager] HTTP API listening on 127.0.0.1:${API_PORT}`)
  pollServer()
})
