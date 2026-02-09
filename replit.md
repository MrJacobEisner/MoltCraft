# Minecraft Java Server on Replit

## Overview
A Minecraft Java Edition server running on Replit using PaperMC and bore (TCP tunnel) to bypass Replit's HTTP-only proxy limitation.

## Architecture
- **PaperMC 1.21.4**: Optimized Minecraft server (listens on port 25565 internally)
- **bore**: TCP tunnel tool that provides a public address (bore.pub:PORT) for players to connect
- **Status Page**: Simple Python HTTP server on port 5000 showing server status, tunnel address, and logs

## How It Works
Replit's networking only supports HTTP traffic. Minecraft uses raw TCP. bore creates a tunnel that bypasses this limitation by providing a public TCP endpoint (bore.pub) that routes directly to the Minecraft server on port 25565.

Note: playit.gg was tried first but its control channel uses UDP, which Replit's network blocks. bore uses pure TCP for everything, so it works on Replit.

## Project Structure
```
├── minecraft-server/
│   ├── server.jar          # PaperMC server (not in git)
│   ├── eula.txt            # EULA acceptance
│   ├── server.properties   # Server config
│   └── start.sh            # JVM startup script
├── status-page/
│   └── server.py           # Web status page (port 5000)
├── bore                    # TCP tunnel binary (not in git)
├── start-all.sh            # Master startup script
└── MINECRAFT_SERVER_PLAN.md # Implementation plan
```

## How to Connect
1. Run the project — it starts the Minecraft server, bore tunnel, and status page
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

## Recent Changes
- 2026-02-09: Switched from playit.gg to bore for tunneling (playit.gg UDP control channel blocked by Replit)
- 2026-02-09: Updated status page to show bore tunnel address automatically
- 2026-02-08: Initial setup with PaperMC 1.21.4 and status page
