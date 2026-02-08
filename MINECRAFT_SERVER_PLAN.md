# Minecraft Java Server on Replit — Implementation Plan

## Overview

This document outlines a plan to run a Minecraft Java Edition server on Replit, using **PaperMC** (an optimized server) and **playit.gg** (a TCP tunneling service) to bypass Replit's HTTP-only proxy limitation.

---

## The Problem

Replit exposes ports through an HTTP reverse proxy. Minecraft clients communicate via raw TCP on port 25565. The proxy doesn't understand Minecraft's protocol, so direct connections fail.

## The Solution

Run the Minecraft server inside Replit's environment and use **playit.gg** as a tunnel. Playit.gg gives us a public TCP address that forwards raw traffic directly to our server, bypassing Replit's HTTP proxy entirely.

```
[Minecraft Client] → (TCP) → [playit.gg public address] → (tunnel) → [Replit: MC Server on port 25565]
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Replit Environment              │
│                                                  │
│  ┌──────────────┐       ┌────────────────────┐  │
│  │  PaperMC     │◄─────►│  playit.gg agent   │  │
│  │  Server      │       │  (TCP tunnel)       │  │
│  │  :25565      │       │                     │  │
│  └──────────────┘       └─────────┬──────────┘  │
│                                    │             │
│  ┌──────────────┐                  │             │
│  │  Web Status  │                  │             │
│  │  Page :5000  │                  │             │
│  └──────────────┘                  │             │
└────────────────────────────────────┼─────────────┘
                                     │
                              ┌──────▼──────┐
                              │  playit.gg  │
                              │  cloud      │
                              │  (public    │
                              │   TCP addr) │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │  Minecraft  │
                              │  Players    │
                              └─────────────┘
```

---

## Step-by-Step Plan

### Phase 1: Environment Setup

**1.1 Install Java**
- Install Java via Replit's module system (GraalVM 22.3 is available, which includes Java 17+)
- Verify `java -version` works

**1.2 Create Directory Structure**
```
/home/runner/minecraft-server/
├── server.jar          # PaperMC server JAR
├── eula.txt            # Minecraft EULA (must accept)
├── server.properties   # Server configuration
├── start.sh            # Server startup script
└── logs/               # Server logs
```

### Phase 2: Minecraft Server Setup

**2.1 Download PaperMC**
- Use the PaperMC API to download the latest stable build
- PaperMC is preferred over vanilla because:
  - Better performance (important given Replit's resource constraints)
  - Plugin support (Bukkit/Spigot compatible)
  - More configuration options for optimization

**2.2 Accept the EULA**
- Create `eula.txt` with `eula=true`

**2.3 Configure server.properties**
Key optimizations for Replit's environment:
```properties
server-port=25565
max-players=5              # Keep low to conserve resources
view-distance=6            # Reduced from default 10
simulation-distance=4      # Reduced to save CPU
online-mode=true           # Mojang authentication
motd=Replit Minecraft Server
```

**2.4 Create startup script**
- Allocate memory carefully (likely 512MB–1GB depending on what's available)
- Use optimized JVM flags for garbage collection
- Run with `nogui` flag

### Phase 3: playit.gg Tunnel Setup

**3.1 Download playit.gg agent**
- Download the Linux AMD64 binary from GitHub releases (v0.17.1)
- Make it executable

**3.2 Initial Setup**
- Run the playit agent — it will output a **claim URL**
- You'll need to:
  1. Visit the claim URL in a browser
  2. Create a free playit.gg account (or log in)
  3. Claim the agent to your account
  4. Create a Minecraft Java tunnel on the dashboard
- The agent will then receive a **public address** (e.g., `something.gl.at.ply.gg:12345`)

**3.3 Configure the tunnel**
- Set local address to `127.0.0.1:25565`
- Tunnel type: Minecraft Java (TCP)

### Phase 4: Web Status Page (Bonus)

**4.1 Simple status dashboard on port 5000**
- A lightweight web page showing:
  - Server status (running / stopped)
  - The playit.gg connection address to share with players
  - Basic instructions for connecting
- This gives us something to display in Replit's webview

### Phase 5: Orchestration

**5.1 Create a master startup script**
- Starts the Minecraft server in the background
- Starts the playit.gg agent in the background
- Starts the web status page on port 5000
- Handles graceful shutdown of all processes

---

## Known Limitations & Risks

| Concern | Detail | Mitigation |
|---------|--------|------------|
| **RAM** | Minecraft needs 1-2GB+ RAM | Use PaperMC optimizations, limit players and view distance |
| **No persistent storage on deploy** | World data lost on republish (VM deployments) | Use during development only; consider backup scripts |
| **playit.gg account required** | Free tier has limits | Free tier supports Minecraft tunnels; paid tier for more |
| **Startup time** | Server takes 30-60s to start | Status page shows loading state |
| **Performance** | May lag with many players | Keep max-players low (3-5), reduce view/simulation distance |

---

## How Players Will Connect

1. Server operator starts the Replit project
2. playit.gg agent connects and provides a public address
3. Share the address with friends (e.g., `abc.gl.at.ply.gg:12345`)
4. Players open Minecraft → Multiplayer → Direct Connection → paste address → Join

---

## Files We'll Create

| File | Purpose |
|------|---------|
| `minecraft-server/start.sh` | Starts the MC server with optimized JVM flags |
| `minecraft-server/eula.txt` | EULA acceptance |
| `minecraft-server/server.properties` | Server configuration |
| `status-page/index.html` | Web status page for Replit webview |
| `status-page/server.py` | Simple HTTP server on port 5000 |
| `start-all.sh` | Master script that launches everything |
| `setup.sh` | One-time setup script (downloads server JAR + playit agent) |

---

## Next Steps

Once this plan is approved, we'll proceed with implementation phase by phase. The whole setup should take about 10-15 minutes, and then you'll need to claim the playit.gg agent in your browser to get the public address.
