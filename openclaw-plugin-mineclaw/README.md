# @openclaw/mineclaw

OpenClaw channel plugin for MineClaw — connect your AI assistant to Minecraft.

Players type `!ai <message>` in Minecraft chat to talk to your AI. The AI can reply, spawn bots, build structures, and explore the world.

## Installation

```bash
openclaw plugins install @openclaw/mineclaw
```

## Configuration

Add to your `openclaw.json`:

```json
{
  "channels": {
    "mineclaw": {
      "enabled": true,
      "apiUrl": "https://your-mineclaw-server.replit.app",
      "apiKey": "your-mineclaw-api-key",
      "webhookPort": 18790,
      "webhookToken": "a-shared-secret"
    }
  }
}
```

### Configuration Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `apiUrl` | Yes | — | URL of your MineClaw server |
| `apiKey` | Yes | — | MineClaw API bearer token |
| `webhookPort` | No | `18790` | Port for the webhook listener that receives Minecraft chat |
| `webhookToken` | No | — | Shared secret for webhook authentication |

## MineClaw Server Setup

On your MineClaw server, set these environment variables to point at your OpenClaw instance:

```
OPENCLAW_WEBHOOK_URL=http://your-openclaw-host:18790/webhook
OPENCLAW_WEBHOOK_TOKEN=a-shared-secret
```

The MineClaw server forwards player messages (prefixed with `!ai`) to this webhook. The plugin receives them and routes them to your AI agent.

## How It Works

### Inbound (Player → AI)
1. Player types `!ai hello` in Minecraft chat
2. MineClaw server forwards the message to the plugin webhook
3. Plugin routes it to your OpenClaw AI agent
4. Agent processes and responds

### Outbound (AI → Player)
1. Agent generates a response
2. Plugin calls MineClaw's `/api/chat/send` API
3. Message appears in Minecraft chat

### Bot Control
The plugin bundles a MineClaw skill that teaches the AI how to:
- Spawn and manage bots in the Minecraft world
- Navigate, fly, teleport bots
- Build structures using fill commands
- Observe the world through bot eyes
- Place blocks, collect items, and interact

## Multi-Account Support

You can connect to multiple MineClaw servers:

```json
{
  "channels": {
    "mineclaw": {
      "enabled": true,
      "apiUrl": "https://server1.replit.app",
      "apiKey": "key1",
      "accounts": {
        "creative": {
          "apiUrl": "https://server2.replit.app",
          "apiKey": "key2",
          "webhookPort": 18791
        }
      }
    }
  }
}
```

## License

MIT
