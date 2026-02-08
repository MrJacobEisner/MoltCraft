# Minecraft Java Server on Replit

## Overview
A Minecraft Java Edition server running on Replit using PaperMC and playit.gg for TCP tunneling.

## Architecture
- **PaperMC 1.21.4**: Optimized Minecraft server (listens on port 25565 internally)
- **playit.gg**: TCP tunnel agent that provides a public address for players to connect
- **Status Page**: Simple Python HTTP server on port 5000 showing server status and logs

## How It Works
Replit's networking only supports HTTP traffic. Minecraft uses raw TCP. playit.gg creates a tunnel that bypasses this limitation by providing a public TCP endpoint that routes directly to the Minecraft server.

## Project Structure
```
├── minecraft-server/
│   ├── server.jar          # PaperMC server (not in git)
│   ├── eula.txt            # EULA acceptance
│   ├── server.properties   # Server config
│   └── start.sh            # JVM startup script
├── status-page/
│   └── server.py           # Web status page (port 5000)
├── playit-linux-amd64      # Tunnel agent binary (not in git)
├── start-all.sh            # Master startup script
└── MINECRAFT_SERVER_PLAN.md # Implementation plan
```

## First-Time Setup
1. Run the project — it starts the Minecraft server, playit.gg agent, and status page
2. Check console logs for the playit.gg **claim URL**
3. Open the claim URL in a browser and create a free playit.gg account
4. Add a Minecraft Java tunnel on the playit.gg dashboard
5. Share the public address with players

## Server Settings
- Max players: 5
- View distance: 6
- Simulation distance: 4
- RAM: 512MB–1024MB
- Game mode: Survival
- Difficulty: Normal

## Recent Changes
- 2026-02-08: Initial setup with PaperMC 1.21.4, playit.gg v0.17.1, and status page
