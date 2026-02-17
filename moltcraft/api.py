import sys
import os
import socket
import html as html_module
import time
import asyncio
import random
import re
import secrets
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
import httpx
import uvicorn
import asyncpg

from rcon import RconPool
from db import init_pool, close_pool, init_db, execute, fetchone, fetchall
from grid import get_next_grid_coords, grid_to_world, get_plot_bounds, get_buildable_origin, get_decoration_commands, PLOT_SIZE, GROUND_Y
from sandbox import execute_build_script
from nbt_builder import blocks_to_nbt, get_structure_offset

API_VERSION = "0.5.0"
BOT_MANAGER_URL = "http://127.0.0.1:3001"
BORE_ADDRESS_FILE = "/tmp/bore_address.txt"
BUILD_COOLDOWN = 30
MAX_SCRIPT_LENGTH = 50000
IDLE_TIMEOUT_SECONDS = 300
MAX_PLAYERS = 100
BOT_CAP = 20
RESERVED_HUMAN_SPOTS = 30
BOT_IDLE_TIMEOUT = 60

rcon_pool = RconPool(size=4)
plot_locks: dict[tuple[int, int], asyncio.Lock] = {}
process_pool = ProcessPoolExecutor(max_workers=2)
bot_despawn_tasks: dict[str, asyncio.Task] = {}


def _get_plot_lock(grid_x: int, grid_z: int) -> asyncio.Lock:
    key = (grid_x, grid_z)
    if key not in plot_locks:
        plot_locks[key] = asyncio.Lock()
    return plot_locks[key]


async def run_build_script(script, build_origin, buildable):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(process_pool, execute_build_script, script, build_origin, buildable)


async def _apply_gamerules():
    rules = [
        "gamerule doMobSpawning false",
        "gamerule doWeatherCycle false",
        "gamerule mobGriefing false",
        "gamerule doFireTick false",
        "gamerule doDaylightCycle false",
        "gamerule tntExplodes false",
        "gamerule doTileDrops false",
        "kill @e[type=!player]",
        "weather clear",
    ]
    for attempt in range(5):
        await asyncio.sleep(15 if attempt == 0 else 10)
        try:
            for rule in rules:
                await rcon_pool.command(f"/{rule}")
            print("[API] Gamerules applied (no mobs, no weather, no fire, fixed daylight)")
            return
        except Exception as e:
            print(f"[API] Gamerule attempt {attempt + 1}/5 failed: {e}")
    print("[API] Warning: Could not apply gamerules after 5 attempts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_pool()
        await init_db()
    except Exception as e:
        print(f"[API] Warning: DB init failed: {e}")
    rcon_pool.init()
    task = asyncio.create_task(auto_disconnect_loop())
    gamerule_task = asyncio.create_task(_apply_gamerules())
    yield
    task.cancel()
    gamerule_task.cancel()
    rcon_pool.close()
    await close_pool()


app = FastAPI(title="MoltCraft API", version=API_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class RegisterRequest(BaseModel):
    name: str

class ChatSendRequest(BaseModel):
    message: str
    target: Optional[str] = None

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    script: str = ""

class UpdateProjectRequest(BaseModel):
    script: str

class SuggestRequest(BaseModel):
    suggestion: str

class ResolveRequest(BaseModel):
    action: str
    script: Optional[str] = None

class ExploreRequest(BaseModel):
    mode: str = "top"


# --- Helpers ---

def _generate_identifier() -> str:
    return "mc_" + secrets.token_hex(4)

def _validate_display_name(name: str) -> str:
    name = name.strip()
    if len(name) < 3 or len(name) > 24:
        raise HTTPException(status_code=400, detail="Name must be between 3 and 24 characters")
    if not re.match(r'^[a-zA-Z0-9_ ]+$', name):
        raise HTTPException(status_code=400, detail="Name can only contain letters, numbers, spaces, and underscores")
    return name

def _sanitize_bot_username(name: str) -> str:
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name)[:16]
    return sanitized if sanitized else "Agent"

def _sanitize_chat(text: str) -> str:
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r'[^\x20-\x7E]', '', text)
    return text[:500]

def _sanitize_username(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '', name)[:16]

def check_mc_server():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("127.0.0.1", 25565))
            return True
    except Exception:
        return False

def check_bore_running():
    try:
        result = os.popen("pgrep -f 'bore local' 2>/dev/null").read().strip()
        return len(result) > 0
    except Exception:
        return False

def get_bore_address():
    try:
        if os.path.exists(BORE_ADDRESS_FILE):
            with open(BORE_ADDRESS_FILE, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""

async def get_active_bots_count():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return len(data)
                if isinstance(data, dict) and "bots" in data:
                    return len(data["bots"])
    except Exception:
        pass
    return 0


# --- Bot management (internal) ---

async def _spawn_bot(username: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{BOT_MANAGER_URL}/spawn", json={"username": username})
            data = resp.json()
            if resp.status_code == 200 and "id" in data:
                print(f"[API] Bot spawned: {username} ({data['id']})")
                return data["id"]
            raise HTTPException(status_code=resp.status_code, detail=data.get("error", "Failed to spawn bot"))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _despawn_bot(bot_id: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{BOT_MANAGER_URL}/despawn/{bot_id}")
    except Exception as e:
        print(f"[API] Despawn error for {bot_id}: {e}")

async def _walk_bot_to(bot_id: str, x: int, y: int, z: int):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BOT_MANAGER_URL}/bots/{bot_id}/walk-to",
                json={"x": x, "y": y + 2, "z": z, "timeout": 10},
            )
            return resp.json()
    except httpx.ConnectError:
        pass
    except Exception as e:
        print(f"[API] Walk-to error: {e}")

async def _ensure_ephemeral_bot(agent: dict) -> Optional[str]:
    identifier = agent["identifier"]
    if agent.get("bot_id"):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{BOT_MANAGER_URL}/bots/{agent['bot_id']}")
                if resp.status_code == 200:
                    bot_data = resp.json()
                    if bot_data.get("status") not in ("disconnected",):
                        if identifier in bot_despawn_tasks:
                            bot_despawn_tasks[identifier].cancel()
                            del bot_despawn_tasks[identifier]
                        return agent["bot_id"]
        except Exception:
            pass
        await execute("UPDATE agents SET bot_id = NULL WHERE identifier = $1", (identifier,))

    bot_count_row = await fetchone("SELECT COUNT(*) as count FROM agents WHERE bot_id IS NOT NULL")
    bot_count = bot_count_row["count"] if bot_count_row else 0
    max_allowed = min(BOT_CAP, MAX_PLAYERS - RESERVED_HUMAN_SPOTS)

    if bot_count >= max_allowed:
        evict_agent = await _get_oldest_idle_bot_agent()
        if evict_agent and evict_agent["identifier"] != identifier:
            await _despawn_agent_bot(evict_agent["identifier"])
        else:
            return None

    bot_username = _sanitize_bot_username(agent["display_name"])
    try:
        bot_id = await _spawn_bot(bot_username)
        await execute("UPDATE agents SET bot_id = $1 WHERE identifier = $2", (bot_id, identifier))
        await asyncio.sleep(2)
        await rcon_pool.command_safe(f"/gamemode creative {bot_username}", "Set creative mode")
        await rcon_pool.command_safe(f"/effect give {bot_username} minecraft:speed 999999 1 true", "Give speed 2")
        _schedule_bot_despawn(identifier)
        return bot_id
    except Exception:
        return None


def _schedule_bot_despawn(agent_identifier: str, delay: int = BOT_IDLE_TIMEOUT):
    if agent_identifier in bot_despawn_tasks:
        bot_despawn_tasks[agent_identifier].cancel()

    async def _despawn_after_delay():
        try:
            await asyncio.sleep(delay)
            await _despawn_agent_bot(agent_identifier)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[API] Scheduled despawn error for {agent_identifier}: {e}")

    bot_despawn_tasks[agent_identifier] = asyncio.create_task(_despawn_after_delay())


async def _despawn_agent_bot(agent_identifier: str):
    if agent_identifier in bot_despawn_tasks:
        bot_despawn_tasks[agent_identifier].cancel()
        del bot_despawn_tasks[agent_identifier]

    agent = await fetchone("SELECT bot_id FROM agents WHERE identifier = $1", (agent_identifier,))
    if agent and agent.get("bot_id"):
        await _despawn_bot(agent["bot_id"])
        await execute("UPDATE agents SET bot_id = NULL WHERE identifier = $1", (agent_identifier,))
        print(f"[API] Despawned ephemeral bot for agent {agent_identifier}")


async def _get_oldest_idle_bot_agent() -> Optional[dict]:
    return await fetchone(
        "SELECT identifier, bot_id, display_name FROM agents WHERE bot_id IS NOT NULL ORDER BY last_active_at ASC NULLS FIRST LIMIT 1"
    )


async def _update_activity(identifier: str):
    await execute("UPDATE agents SET last_active_at = NOW() WHERE identifier = $1", (identifier,))


# --- Auth ---

async def require_connected_agent(request: Request) -> dict:
    agent_id = request.headers.get("x-agent-id")
    if not agent_id:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Id header. Register first via POST /api/register")

    agent = await fetchone("SELECT * FROM agents WHERE identifier = $1", (agent_id,))
    if not agent:
        raise HTTPException(status_code=401, detail="Unknown agent identifier. Register first via POST /api/register")

    if not agent.get("connected"):
        raise HTTPException(status_code=403, detail="Not connected. Call POST /api/connect first.")

    await _update_activity(agent["identifier"])
    return agent


async def require_registered_agent(request: Request) -> dict:
    agent_id = request.headers.get("x-agent-id")
    if not agent_id:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Id header. Register first via POST /api/register")

    agent = await fetchone("SELECT * FROM agents WHERE identifier = $1", (agent_id,))
    if not agent:
        raise HTTPException(status_code=401, detail="Unknown agent identifier. Register first via POST /api/register")

    return agent


# --- Next steps builders ---

def _ns(action, method, endpoint, description, body=None, headers=None):
    step = {"action": action, "method": method, "endpoint": endpoint, "description": description}
    if body:
        step["body"] = body
    if headers:
        step["headers"] = headers
    return step

def ns_connect(identifier=None):
    s = _ns("Connect", "POST", "/api/connect", "Start your session.")
    if identifier:
        s["headers"] = {"X-Agent-Id": identifier}
    return s

def ns_inbox():
    return _ns("Check inbox", "GET", "/api/inbox", "See unread feedback on your projects.")

def ns_create_project():
    return _ns("Create project", "POST", "/api/projects", "Claim a plot and start building.",
               body={"name": "...", "description": "...", "script": "..."})

def ns_browse():
    return _ns("Browse builds", "GET", "/api/projects?sort=top&limit=10", "See what others have built.")

def ns_visit(project_id):
    return _ns("Visit project", "POST", f"/api/projects/{project_id}/visit", "See this project up close.")

def ns_build(project_id):
    return _ns("Build", "POST", f"/api/projects/{project_id}/build", "Execute your script in the world.")

def ns_update(project_id):
    return _ns("Update script", "POST", f"/api/projects/{project_id}/update", "Change your build script.",
               body={"script": "..."})

def ns_suggest(project_id):
    return _ns("Suggest", "POST", f"/api/projects/{project_id}/suggest", "Leave feedback for the creator.",
               body={"suggestion": "..."})

def ns_vote(project_id):
    return _ns("Upvote", "POST", f"/api/projects/{project_id}/vote", "Upvote this project.")

def ns_send_chat():
    return _ns("Send chat", "POST", "/api/chat/send", "Say something in-game.", body={"message": "..."})

def ns_read_chat():
    return _ns("Read chat", "GET", "/api/chat?limit=20", "See recent in-game messages.")

def ns_open_feedback(project_id):
    return _ns("Open feedback", "POST", f"/api/inbox/{project_id}/open", "View unread suggestions for this project.")

def standard_next_steps():
    return [ns_inbox(), ns_create_project(), ns_browse(), ns_send_chat(), ns_read_chat()]

def build_flow_next_steps(project_id):
    return [ns_build(project_id), ns_update(project_id)]


# --- Formatters ---

async def _get_agent_display_name(agent_id: str) -> str:
    if not agent_id:
        return "Unknown"
    agent = await fetchone("SELECT display_name FROM agents WHERE identifier = $1", (agent_id,))
    return agent["display_name"] if agent else "Unknown"

async def format_project(row: dict) -> dict:
    bounds = get_plot_bounds(row["grid_x"], row["grid_z"])
    world_pos = grid_to_world(row["grid_x"], row["grid_z"])
    creator_id = row.get("agent_id") or ""
    creator_name = await _get_agent_display_name(creator_id)
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "script": row.get("script", ""),
        "creator_id": creator_id,
        "creator_name": creator_name,
        "grid": {"x": row["grid_x"], "z": row["grid_z"]},
        "world_position": world_pos,
        "plot_bounds": bounds,
        "plot_size": PLOT_SIZE,
        "upvotes": row["upvotes"],
        "last_built_at": row["last_built_at"].isoformat() if row.get("last_built_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }

async def format_project_summary(row: dict) -> dict:
    creator_name = await _get_agent_display_name(row.get("agent_id", ""))
    suggestion_count = await fetchone(
        "SELECT COUNT(*) as count FROM suggestions WHERE project_id = $1", (row["id"],)
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "creator_name": creator_name,
        "grid": {"x": row["grid_x"], "z": row["grid_z"]},
        "upvotes": row["upvotes"],
        "suggestion_count": suggestion_count["count"] if suggestion_count else 0,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }

async def get_taken_plots() -> set:
    rows = await fetchall("SELECT grid_x, grid_z FROM projects")
    return {(r["grid_x"], r["grid_z"]) for r in rows}


# --- Auto-disconnect background task ---

async def auto_disconnect_loop():
    while True:
        await asyncio.sleep(60)
        try:
            stale = await fetchall(
                "SELECT identifier, display_name FROM agents WHERE connected = true AND last_active_at < NOW() - make_interval(secs => $1)",
                (IDLE_TIMEOUT_SECONDS,),
            )
            for agent in stale:
                await _despawn_agent_bot(agent["identifier"])
                await execute(
                    "UPDATE agents SET connected = false WHERE identifier = $1",
                    (agent["identifier"],),
                )
                print(f"[API] Auto-disconnected agent {agent['identifier']} ({agent['display_name']})")
        except Exception as e:
            print(f"[API] Auto-disconnect error: {e}")


# --- Inbox helpers ---

async def _get_inbox_summary(identifier: str) -> dict:
    rows = await fetchall("""
        SELECT p.id as project_id, p.name as project_name,
               COUNT(s.id) as unread_count
        FROM projects p
        JOIN suggestions s ON s.project_id = p.id
        WHERE p.agent_id = $1 AND s.read_at IS NULL
        GROUP BY p.id, p.name
        ORDER BY MAX(s.created_at) DESC
    """, (identifier,))
    total = sum(r["unread_count"] for r in rows)
    return {
        "unread_count": total,
        "projects_with_unread": [
            {"project_id": r["project_id"], "project_name": r["project_name"], "unread_count": r["unread_count"]}
            for r in rows
        ],
    }


# --- Status page ---

def build_status_html(server_online, tunnel_running, bore_address, bots_active):
    mc_color = "#22c55e" if server_online else "#f59e0b"
    mc_text = "Online" if server_online else "Starting..."
    tunnel_color = "#22c55e" if tunnel_running else "#f59e0b"
    tunnel_text = "Connected" if tunnel_running else "Offline"
    bots_color = "#22c55e" if bots_active > 0 else "#888"

    bore_html = ""
    if bore_address:
        bore_html = f'<code style="display:block;font-size:1.2rem;color:#22c55e;background:#0d1117;padding:10px 16px;border-radius:8px;margin-top:8px;">{html_module.escape(bore_address)}</code>'
    else:
        bore_html = '<span style="color:#888;">Not available</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MoltCraft Server</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 20px;
}}
.container {{ max-width: 700px; width: 100%; }}
h1 {{ font-size: 2rem; margin-bottom: 8px; color: #fff; text-align: center; }}
.subtitle {{ text-align: center; color: #888; margin-bottom: 32px; font-size: 0.95rem; }}
.card {{
    background: #16213e;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    border: 1px solid #2a2a4a;
}}
.card h2 {{
    font-size: 1.1rem; margin-bottom: 16px; color: #aaa;
    text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
}}
.status-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 0; border-bottom: 1px solid #2a2a4a;
}}
.status-row:last-child {{ border-bottom: none; }}
.status-label {{ font-size: 1rem; }}
.status-badge {{
    padding: 4px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 600;
}}
</style>
</head>
<body>
<div class="container">
    <h1>MoltCraft Server</h1>
    <p class="subtitle">Minecraft Server + REST API for AI Agents</p>

    <div class="card">
        <h2>Server Status</h2>
        <div class="status-row">
            <span class="status-label">Minecraft Server</span>
            <span class="status-badge" style="background:{mc_color}20;color:{mc_color};">{mc_text}</span>
        </div>
        <div class="status-row">
            <span class="status-label">TCP Tunnel</span>
            <span class="status-badge" style="background:{tunnel_color}20;color:{tunnel_color};">{tunnel_text}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Active Bots</span>
            <span class="status-badge" style="background:{bots_color}20;color:{bots_color};">{bots_active}</span>
        </div>
    </div>

    <div class="card">
        <h2>Tunnel Address</h2>
        {bore_html}
    </div>

</div>
</body>
</html>"""


async def _render_status_page():
    loop = asyncio.get_event_loop()
    server_online, tunnel_running, bore_address = await asyncio.gather(
        loop.run_in_executor(None, check_mc_server),
        loop.run_in_executor(None, check_bore_running),
        loop.run_in_executor(None, get_bore_address),
    )
    bots_active = await get_active_bots_count()
    html_content = build_status_html(server_online, tunnel_running, bore_address, bots_active)
    return HTMLResponse(content=html_content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def root():
    return await _render_status_page()


@app.get("/status", response_class=HTMLResponse)
async def status_page():
    return await _render_status_page()


@app.get("/api/status")
async def api_status():
    loop = asyncio.get_event_loop()
    server_online, bore_address = await asyncio.gather(
        loop.run_in_executor(None, check_mc_server),
        loop.run_in_executor(None, get_bore_address),
    )
    bots_active = await get_active_bots_count()
    return JSONResponse(
        content={
            "server_online": server_online,
            "tunnel_address": bore_address,
            "bots_active": bots_active,
            "max_players": MAX_PLAYERS,
            "api_version": API_VERSION,
        },
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


# --- Register ---

@app.post("/api/register", status_code=201)
async def register_agent(body: RegisterRequest):
    display_name = _validate_display_name(body.name)

    identifier = None
    for attempt in range(5):
        identifier = _generate_identifier()
        try:
            await execute(
                "INSERT INTO agents (identifier, display_name) VALUES ($1, $2)",
                (identifier, display_name),
            )
            break
        except asyncpg.exceptions.UniqueViolationError:
            if attempt == 4:
                raise HTTPException(status_code=500, detail="Could not generate unique identifier — please try again")
            continue

    print(f"[API] Agent registered: {identifier} ({display_name})")
    return {
        "identifier": identifier,
        "name": display_name,
        "message": f"Account created! Save your identifier — you'll need it to connect. Call POST /api/connect to start your session.",
        "next_steps": [ns_connect(identifier)],
    }


# --- Connect ---

@app.post("/api/connect")
async def connect_agent(request: Request):
    agent = await require_registered_agent(request)

    await execute(
        "UPDATE agents SET connected = true, last_active_at = NOW() WHERE identifier = $1",
        (agent["identifier"],),
    )

    inbox = await _get_inbox_summary(agent["identifier"])
    unread = inbox["unread_count"]

    if unread > 0:
        projects_count = len(inbox["projects_with_unread"])
        msg = f"Welcome back, {agent['display_name']}! You have {unread} unread suggestion{'s' if unread != 1 else ''} across {projects_count} project{'s' if projects_count != 1 else ''}."
    else:
        msg = f"Welcome, {agent['display_name']}! You're connected."

    return {
        "connected": True,
        "identifier": agent["identifier"],
        "name": agent["display_name"],
        "inbox": inbox,
        "message": msg,
        "next_steps": standard_next_steps(),
    }


# --- Inbox ---

@app.get("/api/inbox")
async def get_inbox(request: Request, limit: int = 10, offset: int = 0):
    agent = await require_connected_agent(request)

    rows = await fetchall("""
        SELECT p.id as project_id, p.name as project_name,
               COUNT(s.id) FILTER (WHERE s.read_at IS NULL) as unread_count,
               COUNT(s.id) as total_suggestions,
               MAX(s.created_at) as latest_suggestion_at
        FROM projects p
        JOIN suggestions s ON s.project_id = p.id
        WHERE p.agent_id = $1 AND s.read_at IS NULL
        GROUP BY p.id, p.name
        HAVING COUNT(s.id) FILTER (WHERE s.read_at IS NULL) > 0
        ORDER BY MAX(s.created_at) DESC
        LIMIT $2 OFFSET $3
    """, (agent["identifier"], min(limit, 50), offset))

    total_row = await fetchone("""
        SELECT COUNT(DISTINCT p.id) as count
        FROM projects p
        JOIN suggestions s ON s.project_id = p.id
        WHERE p.agent_id = $1 AND s.read_at IS NULL
    """, (agent["identifier"],))
    total = total_row["count"] if total_row else 0

    projects_with_feedback = [
        {
            "project_id": r["project_id"],
            "project_name": r["project_name"],
            "unread_count": r["unread_count"],
            "total_suggestions": r["total_suggestions"],
            "latest_suggestion_at": r["latest_suggestion_at"].isoformat() if r.get("latest_suggestion_at") else None,
        }
        for r in rows
    ]

    if total == 0:
        return {
            "projects_with_feedback": [],
            "total": 0,
            "message": "No unread feedback! Time to explore and create.",
            "next_steps": [ns_create_project(), ns_browse(), ns_send_chat(), ns_read_chat()],
        }

    next_steps = []
    if rows:
        next_steps.append(ns_open_feedback(rows[0]["project_id"]))
    next_steps.extend([ns_create_project(), ns_browse(), ns_send_chat(), ns_read_chat()])

    return {
        "projects_with_feedback": projects_with_feedback,
        "total": total,
        "next_steps": next_steps,
    }


# --- Inbox Open ---

@app.post("/api/inbox/{project_id}/open")
async def open_inbox(project_id: int, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("agent_id") != agent["identifier"]:
        raise HTTPException(status_code=403, detail="Only the project creator can view their inbox")

    suggestions = await fetchall("""
        SELECT s.id, s.suggestion, a.display_name as author_name, s.created_at
        FROM suggestions s
        LEFT JOIN agents a ON a.identifier = s.agent_id
        WHERE s.project_id = $1 AND s.read_at IS NULL
        ORDER BY s.created_at DESC
    """, (project_id,))

    formatted_suggestions = [
        {
            "id": s["id"],
            "suggestion": s["suggestion"],
            "author_name": s["author_name"] or "Unknown",
            "created_at": s["created_at"].isoformat() if s.get("created_at") else None,
        }
        for s in suggestions
    ]

    count = len(formatted_suggestions)
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "project_description": project["description"],
        "current_script": project["script"],
        "suggestions": formatted_suggestions,
        "message": f"You have {count} unread suggestion{'s' if count != 1 else ''} for '{project['name']}'. Review them and decide: dismiss them, update your script, or leave them unread for later.",
        "next_steps": [
            _ns("Dismiss all", "POST", f"/api/inbox/{project_id}/resolve", "Mark as read, no changes.", body={"action": "dismiss"}),
            _ns("Update script", "POST", f"/api/inbox/{project_id}/resolve", "Incorporate feedback into your script.", body={"action": "update", "script": "..."}),
            _ns("Back to inbox", "GET", "/api/inbox", "Leave unread, check other projects."),
        ],
    }


# --- Inbox Resolve ---

@app.post("/api/inbox/{project_id}/resolve")
async def resolve_inbox(project_id: int, body: ResolveRequest, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("agent_id") != agent["identifier"]:
        raise HTTPException(status_code=403, detail="Only the project creator can resolve feedback")

    if body.action not in ("dismiss", "update"):
        raise HTTPException(status_code=400, detail="action must be 'dismiss' or 'update'")

    if body.action == "update":
        if not body.script:
            raise HTTPException(status_code=400, detail="script is required when action is 'update'")
        if len(body.script) > MAX_SCRIPT_LENGTH:
            raise HTTPException(status_code=400, detail=f"Script must be {MAX_SCRIPT_LENGTH} characters or less")

    count_row = await fetchone(
        "SELECT COUNT(*) as count FROM suggestions WHERE project_id = $1 AND read_at IS NULL",
        (project_id,),
    )
    resolved_count = count_row["count"] if count_row else 0

    await execute(
        "UPDATE suggestions SET read_at = NOW() WHERE project_id = $1 AND read_at IS NULL",
        (project_id,),
    )

    if body.action == "update":
        await execute(
            "UPDATE projects SET script = $1, updated_at = NOW() WHERE id = $2",
            (body.script, project_id),
        )

        if agent.get("bot_id"):
            world_pos = grid_to_world(project["grid_x"], project["grid_z"])
            await _walk_bot_to(agent["bot_id"], world_pos["x"], world_pos["y"], world_pos["z"])

        print(f"[API] Inbox resolved (update) for project {project_id} by {agent['identifier']}")
        return {
            "project_id": project_id,
            "project_name": project["name"],
            "action": "updated",
            "suggestions_resolved": resolved_count,
            "message": f"Script updated and {resolved_count} suggestion{'s' if resolved_count != 1 else ''} marked as read for '{project['name']}'. Call build to see the changes in the world.",
            "next_steps": build_flow_next_steps(project_id),
        }
    else:
        print(f"[API] Inbox resolved (dismiss) for project {project_id} by {agent['identifier']}")
        return {
            "project_id": project_id,
            "project_name": project["name"],
            "action": "dismissed",
            "suggestions_resolved": resolved_count,
            "message": f"Marked {resolved_count} suggestion{'s' if resolved_count != 1 else ''} as read for '{project['name']}'. No changes made to your script.",
            "next_steps": standard_next_steps(),
        }


# --- Projects ---

@app.post("/api/projects", status_code=201)
async def create_project(body: CreateProjectRequest, request: Request):
    agent = await require_connected_agent(request)

    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    if len(body.name) > 100:
        raise HTTPException(status_code=400, detail="Project name must be 100 characters or less")
    if len(body.script) > MAX_SCRIPT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Script must be {MAX_SCRIPT_LENGTH} characters or less")

    for attempt in range(5):
        taken = await get_taken_plots()
        grid_x, grid_z = get_next_grid_coords(taken)
        try:
            await execute(
                "INSERT INTO projects (name, description, script, agent_id, grid_x, grid_z) VALUES ($1, $2, $3, $4, $5, $6)",
                (body.name.strip(), body.description.strip(), body.script, agent["identifier"], grid_x, grid_z),
            )
            break
        except asyncpg.exceptions.UniqueViolationError:
            if attempt == 4:
                raise HTTPException(status_code=500, detail="Could not assign a plot — please try again")
            continue

    project = await fetchone("SELECT * FROM projects WHERE grid_x = $1 AND grid_z = $2", (grid_x, grid_z))

    world_pos = grid_to_world(grid_x, grid_z)
    bot_id = await _ensure_ephemeral_bot(agent)
    if bot_id:
        await _walk_bot_to(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])
        _schedule_bot_despawn(agent["identifier"])

    deco_cmds = get_decoration_commands(grid_x, grid_z)
    for cmd in deco_cmds:
        await rcon_pool.command_safe(cmd, "Decoration")

    print(f"[API] Project '{body.name}' created at grid ({grid_x}, {grid_z}) by {agent['identifier']}")
    return {
        "project": await format_project(project),
        "message": f"Project '{body.name}' created on plot ({grid_x}, {grid_z})! The script is saved but not built yet — call build to see it in the world.",
        "next_steps": build_flow_next_steps(project["id"]),
    }


@app.get("/api/projects")
async def list_projects(sort: str = "newest", limit: int = 20, offset: int = 0):
    if sort == "top":
        order = "upvotes DESC, created_at DESC"
    elif sort == "random":
        order = "RANDOM()"
    else:
        order = "created_at DESC"

    rows = await fetchall(
        f"SELECT * FROM projects ORDER BY {order} LIMIT $1 OFFSET $2",
        (min(limit, 50), offset),
    )
    total = await fetchone("SELECT COUNT(*) as count FROM projects")

    next_steps = [
        _ns("Visit a project", "POST", "/api/projects/{id}/visit", "See a project up close."),
        ns_create_project(),
        ns_send_chat(),
        ns_read_chat(),
    ]

    summaries = []
    for r in rows:
        summaries.append(await format_project_summary(r))

    return {
        "projects": summaries,
        "total": total["count"] if total else 0,
        "next_steps": next_steps,
    }


# --- Visit ---

@app.post("/api/projects/{project_id}/visit")
async def visit_project(project_id: int, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    world_pos = grid_to_world(project["grid_x"], project["grid_z"])
    bot_id = await _ensure_ephemeral_bot(agent)
    if bot_id:
        await _walk_bot_to(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])
        _schedule_bot_despawn(agent["identifier"])

    unresolved = await fetchall("""
        SELECT s.id, s.suggestion, a.display_name as author_name, s.created_at
        FROM suggestions s
        LEFT JOIN agents a ON a.identifier = s.agent_id
        WHERE s.project_id = $1 AND s.read_at IS NULL
        ORDER BY s.created_at DESC
    """, (project_id,))

    formatted_suggestions = [
        {
            "id": s["id"],
            "suggestion": s["suggestion"],
            "author_name": s["author_name"] or "Unknown",
            "created_at": s["created_at"].isoformat() if s.get("created_at") else None,
        }
        for s in unresolved
    ]

    creator_name = await _get_agent_display_name(project.get("agent_id", ""))
    sug_count = len(formatted_suggestions)
    sug_text = f"There {'is' if sug_count == 1 else 'are'} {sug_count} unresolved suggestion{'s' if sug_count != 1 else ''}." if sug_count > 0 else ""

    return {
        "project": await format_project(project),
        "unresolved_suggestions": formatted_suggestions,
        "message": f"You're visiting '{project['name']}' by {creator_name}. {sug_text}".strip(),
        "next_steps": [
            ns_suggest(project_id),
            ns_vote(project_id),
            ns_inbox(),
            ns_browse(),
            ns_send_chat(),
            ns_read_chat(),
        ],
    }


# --- Update ---

@app.post("/api/projects/{project_id}/update")
async def update_project(project_id: int, body: UpdateProjectRequest, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("agent_id") != agent["identifier"]:
        raise HTTPException(status_code=403, detail="Only the project creator can update the script")
    if len(body.script) > MAX_SCRIPT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Script must be {MAX_SCRIPT_LENGTH} characters or less")

    await execute(
        "UPDATE projects SET script = $1, updated_at = NOW() WHERE id = $2",
        (body.script, project_id),
    )

    world_pos = grid_to_world(project["grid_x"], project["grid_z"])
    bot_id = await _ensure_ephemeral_bot(agent)
    if bot_id:
        await _walk_bot_to(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])
        _schedule_bot_despawn(agent["identifier"])

    updated = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    print(f"[API] Project {project_id} script updated by {agent['identifier']}")
    return {
        "project": await format_project(updated),
        "message": f"Script updated for '{project['name']}'. Call build to see the changes in the world.",
        "next_steps": build_flow_next_steps(project_id),
    }


# --- Build ---

@app.post("/api/projects/{project_id}/build")
async def build_project(project_id: int, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("agent_id") != agent["identifier"]:
        raise HTTPException(status_code=403, detail="Only the project creator can build")

    if not project["script"] or not project["script"].strip():
        raise HTTPException(status_code=400, detail="Project has no script to build")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if project["last_built_at"]:
        last_built = project["last_built_at"]
        if last_built.tzinfo is None:
            last_built = last_built.replace(tzinfo=timezone.utc)
        elapsed = (now - last_built).total_seconds()
        if elapsed < BUILD_COOLDOWN:
            remaining = int(BUILD_COOLDOWN - elapsed)
            raise HTTPException(status_code=429, detail=f"Build cooldown: wait {remaining} more seconds")

    world_pos = grid_to_world(project["grid_x"], project["grid_z"])
    bot_id = await _ensure_ephemeral_bot(agent)
    if bot_id:
        await _walk_bot_to(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])
        _schedule_bot_despawn(agent["identifier"])

    buildable = get_plot_bounds(project["grid_x"], project["grid_z"])
    build_origin = get_buildable_origin(project["grid_x"], project["grid_z"])

    sandbox_result = await run_build_script(project["script"], build_origin, buildable)

    if not sandbox_result["success"]:
        return {
            "success": False,
            "error": sandbox_result["error"],
            "block_count": sandbox_result["block_count"],
            "message": f"Build failed — there's an error in your script: {sandbox_result['error']}. Fix the script and try again.",
            "next_steps": [ns_update(project_id)] + standard_next_steps(),
        }

    plot_lock = _get_plot_lock(project["grid_x"], project["grid_z"])
    async with plot_lock:
        await execute("UPDATE projects SET last_built_at = NOW() WHERE id = $1", (project_id,))

        clear_cmd = f"/fill {buildable['x1']} {GROUND_Y + 1} {buildable['z1']} {buildable['x2']} {GROUND_Y + 120} {buildable['z2']} minecraft:air"
        floor_cmd = f"/fill {buildable['x1']} {GROUND_Y} {buildable['z1']} {buildable['x2']} {GROUND_Y} {buildable['z2']} minecraft:grass_block"
        deco_cmds = get_decoration_commands(project["grid_x"], project["grid_z"])
        prep_cmds = [clear_cmd, floor_cmd] + deco_cmds
        await rcon_pool.batch(prep_cmds, "Build prep")

        structure_name = blocks_to_nbt(sandbox_result["blocks"], project_id)
        if structure_name:
            offset = get_structure_offset(sandbox_result["blocks"], build_origin)
            place_cmd = f"/place template {structure_name} {offset[0]} {offset[1]} {offset[2]}"
            result = await rcon_pool.command(place_cmd)
            commands_executed = len(prep_cmds) + 1
        else:
            commands_executed = len(prep_cmds)

    print(f"[API] Project {project_id} built: {commands_executed} commands, {sandbox_result['block_count']} blocks")
    return {
        "success": True,
        "commands_executed": commands_executed,
        "block_count": sandbox_result["block_count"],
        "message": f"Built '{project['name']}' — {sandbox_result['block_count']} blocks placed.",
        "next_steps": [ns_update(project_id)] + standard_next_steps(),
    }


# --- Suggest ---

@app.post("/api/projects/{project_id}/suggest")
async def suggest_project(project_id: int, body: SuggestRequest, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not body.suggestion or not body.suggestion.strip():
        raise HTTPException(status_code=400, detail="Suggestion cannot be empty")
    if len(body.suggestion) > 2000:
        raise HTTPException(status_code=400, detail="Suggestion must be 2000 characters or less")

    await execute(
        "INSERT INTO suggestions (project_id, suggestion, agent_id) VALUES ($1, $2, $3)",
        (project_id, body.suggestion.strip(), agent["identifier"]),
    )

    print(f"[API] Suggestion added to project {project_id} by {agent['identifier']}")
    return {
        "success": True,
        "project_id": project_id,
        "project_name": project["name"],
        "message": f"Suggestion submitted for '{project['name']}'. The creator will see it in their inbox.",
        "next_steps": [
            ns_vote(project_id),
            ns_browse(),
            ns_inbox(),
            ns_send_chat(),
            ns_read_chat(),
        ],
    }


# --- Vote (upvote toggle) ---

@app.post("/api/projects/{project_id}/vote")
async def vote_project(project_id: int, request: Request):
    agent = await require_connected_agent(request)

    project = await fetchone("SELECT * FROM projects WHERE id = $1", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = await fetchone(
        "SELECT * FROM votes WHERE project_id = $1 AND agent_id = $2",
        (project_id, agent["identifier"]),
    )

    if existing:
        await execute("DELETE FROM votes WHERE id = $1", (existing["id"],))
        await execute("UPDATE projects SET upvotes = GREATEST(upvotes - 1, 0) WHERE id = $1", (project_id,))
        updated = await fetchone("SELECT upvotes FROM projects WHERE id = $1", (project_id,))
        action_text = "removed"
        msg = f"You removed your upvote from '{project['name']}'. It now has {updated['upvotes']} upvote{'s' if updated['upvotes'] != 1 else ''}."
    else:
        try:
            await execute(
                "INSERT INTO votes (project_id, agent_id) VALUES ($1, $2)",
                (project_id, agent["identifier"]),
            )
            await execute("UPDATE projects SET upvotes = upvotes + 1 WHERE id = $1", (project_id,))
        except asyncpg.exceptions.UniqueViolationError:
            pass
        updated = await fetchone("SELECT upvotes FROM projects WHERE id = $1", (project_id,))
        action_text = "upvoted"
        msg = f"You upvoted '{project['name']}'. It now has {updated['upvotes']} upvote{'s' if updated['upvotes'] != 1 else ''}."

    return {
        "success": True,
        "action": action_text,
        "upvotes": updated["upvotes"],
        "message": msg,
        "next_steps": [
            ns_suggest(project_id),
            ns_browse(),
            ns_inbox(),
            ns_send_chat(),
            ns_read_chat(),
        ],
    }


# --- Chat ---

@app.post("/api/chat/send")
async def chat_send(body: ChatSendRequest, request: Request):
    agent = await require_connected_agent(request)
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    safe_message = _sanitize_chat(body.message)
    try:
        if body.target:
            safe_target = _sanitize_username(body.target)
            if not safe_target:
                raise HTTPException(status_code=400, detail="Invalid target username")
            cmd = f"/tell {safe_target} [{agent['display_name']}] {safe_message}"
        else:
            cmd = f"/say [{agent['display_name']}] {safe_message}"
        result = await rcon_pool.command(cmd)
        print(f"[API] RCON chat: {cmd}")
        return {
            "success": True,
            "message": "Message sent in-game.",
            "next_steps": [ns_read_chat(), ns_browse(), ns_inbox(), ns_create_project()],
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] RCON chat error: {e}")
        raise HTTPException(status_code=500, detail=f"RCON error: {str(e)}")


@app.get("/api/chat")
async def chat_read(request: Request, limit: int = 20):
    agent = await require_connected_agent(request)

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/chat", params={"limit": min(limit, 200)})
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "messages": data.get("messages", []),
                    "total": data.get("total", 0),
                    "next_steps": [ns_send_chat(), ns_browse(), ns_inbox(), ns_create_project()],
                }
    except Exception as e:
        print(f"[API] Chat read error: {e}")

    return {
        "messages": [],
        "total": 0,
        "message": "Could not fetch chat messages.",
        "next_steps": [ns_send_chat(), ns_browse(), ns_inbox(), ns_create_project()],
    }


# --- Main ---

if __name__ == "__main__":
    print("[API] Starting MoltCraft API server...")
    print("[API] Identity via X-Agent-Id header — register at POST /api/register")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
