# Minecraft Java Server on Replit

## Overview
A Minecraft Java Edition server running on Replit using PaperMC and bore (TCP tunnel) to bypass Replit's HTTP-only proxy limitation. Features an AI Builder system that lets players use AI models (Claude, OpenAI, Gemini, OpenRouter) to generate and place structures in-game via chat commands.

## Architecture
- **PaperMC 1.21.11**: Optimized Minecraft server (listens on port 25565 internally)
- **bore**: TCP tunnel tool that provides a public address (bore.pub:PORT) for players to connect
- **Status Page**: Simple Python HTTP server on port 5000 showing server status, tunnel address, and logs
- **AI Builder**: Python chat watcher that monitors in-game chat for !commands, sends prompts to AI models, and executes generated build scripts via RCON

## How It Works
Replit's networking only supports HTTP traffic. Minecraft uses raw TCP. bore creates a tunnel that bypasses this limitation by providing a public TCP endpoint (bore.pub) that routes directly to the Minecraft server on port 25565.

Note: playit.gg was tried first but its control channel uses UDP, which Replit's network blocks. bore uses pure TCP for everything, so it works on Replit.

## AI Builder System
Players can type commands in Minecraft chat to have AI models build structures:

### Commands
- `!claude <prompt>` - Build with Claude Opus 4.5 (default)
- `!claude:sonnet <prompt>` - Build with Claude Sonnet 4.5
- `!claude:haiku <prompt>` - Build with Claude Haiku 4.5
- `!openai <prompt>` - Build with GPT-5.2 (default)
- `!openai:o4-mini <prompt>` - Build with o4-mini
- `!gemini <prompt>` - Build with Gemini 3 Pro (default)
- `!gemini:flash <prompt>` - Build with Gemini 3 Flash
- `!openrouter:deepseek <prompt>` - Build with DeepSeek R1
- `!openrouter:llama <prompt>` - Build with Llama 3
- `!help` - Show available commands
- `!models` - Show all available models

### How AI Building Works
1. Player types `!claude build a castle` in chat
2. Chat watcher detects the command in the server log
3. Gets the player's position via RCON
4. Sends the prompt to the selected AI model with a system prompt containing the MinecraftBuilder API
5. AI generates a Python script using the builder library
6. Script is executed, generating Minecraft /setblock and /fill commands
7. Commands are sent to the server via RCON, placing blocks in the world

### AI Integrations
All four providers use Replit AI Integrations (no API keys needed, billed to Replit credits):
- Anthropic (Claude) - claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5
- OpenAI - gpt-5.2, gpt-5.1, gpt-5-mini, o4-mini, o3
- Gemini - gemini-3-pro-preview, gemini-3-flash-preview, gemini-2.5-pro
- OpenRouter - deepseek, llama, qwen, mistral, gemma (and more via model name)

## Project Structure
```
├── minecraft-server/
│   ├── server.jar          # PaperMC server (not in git)
│   ├── eula.txt            # EULA acceptance
│   ├── server.properties   # Server config (RCON enabled)
│   └── start.sh            # JVM startup script
├── ai-builder/
│   ├── chat_watcher.py     # Main: watches chat log, triggers AI builds
│   ├── ai_providers.py     # Multi-model AI engine (Claude, OpenAI, Gemini, OpenRouter)
│   ├── mc_builder.py       # Building helper library (place_block, fill, sphere, etc.)
│   └── rcon_client.py      # RCON client for sending commands to MC server
├── status-page/
│   └── server.py           # Web status page (port 5000)
├── bore                    # TCP tunnel binary (not in git)
├── start-all.sh            # Master startup script
└── MINECRAFT_SERVER_PLAN.md # Implementation plan
```

## How to Connect
1. Run the project — it starts the Minecraft server, bore tunnel, status page, and AI builder
2. The status page will show the server address (e.g., bore.pub:20570) once the tunnel connects
3. In Minecraft: Multiplayer -> Direct Connection -> paste the address
4. Note: The port changes each time the server restarts

## Server Settings
- Max players: 5
- View distance: 6
- Simulation distance: 4
- RAM: 512MB–1024MB
- Game mode: Survival
- Difficulty: Normal
- RCON: Enabled on port 25575

## Recent Changes
- 2026-02-09: Added AI Builder system with Claude, OpenAI, Gemini, and OpenRouter support
- 2026-02-09: Upgraded PaperMC from 1.21.4 to 1.21.11 (fix "Outdated server" error)
- 2026-02-09: Switched from playit.gg to bore for tunneling (playit.gg UDP control channel blocked by Replit)
- 2026-02-09: Updated status page to show bore tunnel address automatically
- 2026-02-08: Initial setup with PaperMC 1.21.4 and status page
