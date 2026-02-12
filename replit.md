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
7. Script is executed in a secure sandbox, collecting block placements in memory
8. Fill-region optimizer merges same-type adjacent blocks into minimal rectangular regions
9. Optimized `/fill` and `/setblock` commands are sent directly via RCON (no datapack reload needed)

### Plugin Architecture
- **Java Plugin** (`ai-builder-plugin/`): Registers slash commands, provides tab-completion (model variants + example prompts), writes JSON command files to `plugins/AIBuilder/queue/`
- **Python Backend** (`ai-builder/`): Polls the queue directory, processes commands, calls AI APIs, generates optimized /fill commands, places them via RCON
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
├── ai-builder/
│   ├── chat_watcher.py     # Main: polls plugin queue + watches chat log
│   ├── ai_providers.py     # Multi-model AI engine (Claude, OpenAI, Gemini, OpenRouter)
│   ├── mc_builder.py       # Block builder + fill-region optimizer (direct RCON placement)
│   ├── rcon_client.py      # RCON client for sending commands to MC server
│   ├── boss_bar.py         # Animated boss bar progress indicator during builds
│   └── build_book.py       # Written book generator with build report stats
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
│   ├── server.py           # Web status page (port 5000)
│   └── template.html       # HTML template for status page
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
- View distance: 16
- Simulation distance: 4
- RAM: 1GB–4GB
- Game mode: Creative (forced)
- World type: Superflat
- Difficulty: Peaceful
- RCON: Enabled on port 25575

## Recent Changes
- 2026-02-12: AI now builds at origin (0,0,0) and backend auto-offsets to player position — models no longer need to handle positioning
- 2026-02-12: AI system prompt updated to require a plan before code; explanation shown to player in chat before building
- 2026-02-12: Increased view distance from 6 to 16 chunks
- 2026-02-11: Added animated boss bar during AI builds (pulsing colors while thinking, phase updates) and written book build reports (prompt, model, tokens, cost, coordinates, code)
- 2026-02-11: Major code cleanup — unified AI provider dispatch, decomposed process_command, extracted HTML template, fixed XSS/type-safety issues, removed dead code, no command limit
- 2026-02-11: Replaced NBT/datapack placement with direct RCON /fill commands — fill-region optimizer merges blocks, no more slow datapack reloads
- 2026-02-09: Expanded sandbox imports: added random, itertools, functools, collections, string, colorsys, copy; increased JVM memory to 1536MB; removed block limit
- 2026-02-09: Added AI error retry system — failed builds feed error messages back to the AI for up to 3 attempts, with player-visible progress messages
- 2026-02-09: Added PaperMC Java plugin for /slash commands with tab-completion (replaced !chat commands)
- 2026-02-09: Switched to superflat world in creative mode
- 2026-02-09: Added AI Builder system with Claude, OpenAI, Gemini, and OpenRouter support
- 2026-02-09: Upgraded PaperMC from 1.21.4 to 1.21.11 (fix "Outdated server" error)
- 2026-02-09: Switched from playit.gg to bore for tunneling (playit.gg UDP control channel blocked by Replit)
- 2026-02-09: Updated status page to show bore tunnel address automatically
- 2026-02-08: Initial setup with PaperMC 1.21.4 and status page
