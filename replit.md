# Minecraft Java Server on Replit

## Overview
A Minecraft Java Edition server running on Replit using PaperMC and bore (TCP tunnel) to bypass Replit's HTTP-only proxy limitation. Features an AI Builder system that lets players use AI models (Claude, OpenAI, Gemini, OpenRouter) to generate and place structures in-game via slash commands.

## Architecture
- **PaperMC 1.21.11**: Optimized Minecraft server (listens on port 25565 internally)
- **bore**: TCP tunnel tool that provides a public address (bore.pub:PORT) for players to connect
- **Status Page**: Simple Python HTTP server on port 5000 showing server status, tunnel address, and logs
- **AI Builder Plugin**: Java PaperMC plugin that registers /claude, /openai, /gemini, /openrouter commands with tab-completion
- **AI Builder Backend**: Python chat watcher that picks up commands from the plugin queue, sends prompts to AI models, and places generated structures via RCON

## How It Works
Replit's networking only supports HTTP traffic. Minecraft uses raw TCP. bore creates a tunnel that bypasses this limitation by providing a public TCP endpoint (bore.pub) that routes directly to the Minecraft server on port 25565.

Note: playit.gg was tried first but its control channel uses UDP, which Replit's network blocks. bore uses pure TCP for everything, so it works on Replit.

## AI Builder System
Players use slash commands in Minecraft to have AI models build structures:

### Commands
- `/claude <prompt>` - Build with Claude Opus 4.5 (default)
- `/claude :sonnet <prompt>` - Build with Claude Sonnet 4.5
- `/claude :haiku <prompt>` - Build with Claude Haiku 4.5
- `/openai <prompt>` - Build with GPT-5.2 (default)
- `/openai :o4-mini <prompt>` - Build with o4-mini
- `/gemini <prompt>` - Build with Gemini 3 Pro (default)
- `/gemini :flash <prompt>` - Build with Gemini 3 Flash
- `/openrouter :deepseek <prompt>` - Build with DeepSeek R1
- `/openrouter :llama <prompt>` - Build with Llama 3
- `/aihelp` - Show available commands
- `/models` - Show all available models

### How AI Building Works
1. Player types `/claude build a castle` in chat
2. The Java plugin catches the command, shows tab-complete hints, and writes a JSON file to the queue folder
3. Python chat watcher picks up the queued command
4. Gets the player's position via RCON
5. Sends the prompt to the selected AI model with a system prompt containing the MinecraftBuilder API
6. AI generates a Python script using the builder library
7. Script is executed in a secure sandbox, building an NBT structure in memory
8. Structure is saved as a .nbt file to the AI builder datapack
9. Server reloads datapacks, then `/place template` places the entire structure instantly

### Plugin Architecture
- **Java Plugin** (`ai-builder-plugin/`): Registers slash commands, provides tab-completion (model variants + example prompts), writes JSON command files to `plugins/AIBuilder/queue/`
- **Python Backend** (`ai-builder/`): Polls the queue directory, processes commands, calls AI APIs, generates NBT structures, places them via RCON
- **Communication**: Plugin writes JSON files (`{player, command, prompt, timestamp}`) to the queue dir; Python reads and deletes them

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
│   ├── server.properties   # Server config (RCON enabled, creative, superflat)
│   ├── start.sh            # JVM startup script
│   ├── plugins/
│   │   └── AIBuilder.jar   # AI Builder plugin (compiled)
│   └── world/datapacks/ai-builder/  # Datapack for AI-generated structures
│       ├── pack.mcmeta
│       └── data/ai/structures/      # .nbt files saved here temporarily
├── ai-builder/
│   ├── chat_watcher.py     # Main: polls plugin queue + watches chat log
│   ├── ai_providers.py     # Multi-model AI engine (Claude, OpenAI, Gemini, OpenRouter)
│   ├── mc_builder.py       # NBT structure builder (uses nbt-structure-utils)
│   └── rcon_client.py      # RCON client for sending commands to MC server
├── ai-builder-plugin/
│   ├── src/com/aibuilder/  # Java plugin source
│   │   ├── AIBuilderPlugin.java
│   │   ├── AICommandExecutor.java
│   │   └── AITabCompleter.java
│   ├── resources/plugin.yml
│   ├── libs/               # Paper API + Adventure API JARs (not in git)
│   ├── build.sh            # Compile + install plugin
│   └── AIBuilder.jar       # Compiled plugin JAR
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
- Game mode: Creative (forced)
- World type: Superflat
- Difficulty: Normal
- RCON: Enabled on port 25575

## Recent Changes
- 2026-02-09: Added PaperMC Java plugin for /slash commands with tab-completion (replaced !chat commands)
- 2026-02-09: Switched AI Builder to NBT-based placement (instant structure placement via /place template)
- 2026-02-09: Switched to superflat world in creative mode
- 2026-02-09: Added AI Builder system with Claude, OpenAI, Gemini, and OpenRouter support
- 2026-02-09: Upgraded PaperMC from 1.21.4 to 1.21.11 (fix "Outdated server" error)
- 2026-02-09: Switched from playit.gg to bore for tunneling (playit.gg UDP control channel blocked by Replit)
- 2026-02-09: Updated status page to show bore tunnel address automatically
- 2026-02-08: Initial setup with PaperMC 1.21.4 and status page
