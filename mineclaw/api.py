import sys
import os
import socket
import html as html_module
import time
import asyncio
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import httpx
import uvicorn

from rcon import RconClient
from db import execute, fetchone, fetchall
from grid import get_next_grid_coords, grid_to_world, get_plot_bounds, get_buildable_origin, get_decoration_commands, PLOT_SIZE, GROUND_Y
from sandbox import execute_build_script

API_VERSION = "0.2.0"
BOT_MANAGER_URL = "http://127.0.0.1:3001"
BORE_ADDRESS_FILE = "/tmp/bore_address.txt"
BUILD_COOLDOWN = 30
MAX_SCRIPT_LENGTH = 50000

rcon_client = RconClient()

ip_to_bot = {}

build_lock = asyncio.Lock()

app = FastAPI(title="MoltCraft API", version=API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_bot_id_for_ip(ip: str) -> Optional[str]:
    return ip_to_bot.get(ip)


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


class VoteRequest(BaseModel):
    direction: int


class ExploreRequest(BaseModel):
    mode: str = "top"


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
    <p class="subtitle">Minecraft Server + REST API</p>

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
    server_online = check_mc_server()
    tunnel_running = check_bore_running()
    bore_address = get_bore_address()
    bots_active = await get_active_bots_count()
    html_content = build_status_html(server_online, tunnel_running, bore_address, bots_active)
    return HTMLResponse(content=html_content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/", response_class=HTMLResponse)
async def root():
    return await _render_status_page()


@app.get("/status", response_class=HTMLResponse)
async def status_page():
    return await _render_status_page()


@app.get("/api/status")
async def api_status():
    server_online = check_mc_server()
    bore_address = get_bore_address()
    bots_active = await get_active_bots_count()
    return JSONResponse(
        content={
            "server_online": server_online,
            "tunnel_address": bore_address,
            "bots_active": bots_active,
            "api_version": API_VERSION,
        },
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def _sanitize_chat(text: str) -> str:
    import re
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r'[^\x20-\x7E]', '', text)
    return text[:500]


def _sanitize_username(name: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '', name)[:16]


def _username_from_ip(ip: str) -> str:
    import hashlib
    try:
        last_octet = ip.split(".")[-1]
        return f"Agent_{last_octet}"
    except Exception:
        short_hash = hashlib.md5(ip.encode()).hexdigest()[:6]
        return f"Agent_{short_hash}"


async def _spawn_bot_for_ip(client_ip: str) -> str:
    username = _username_from_ip(client_ip)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{BOT_MANAGER_URL}/spawn", json={"username": username})
            data = resp.json()
            if resp.status_code == 200 and "id" in data:
                ip_to_bot[client_ip] = data["id"]
                print(f"[API] Bot {data['id']} auto-spawned for IP {client_ip} as {username}")
                return data["id"]
            raise HTTPException(status_code=resp.status_code, detail=data.get("error", "Failed to spawn bot"))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def require_bot(request: Request) -> str:
    client_ip = get_client_ip(request)
    bot_id = get_bot_id_for_ip(client_ip)

    if bot_id:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{BOT_MANAGER_URL}/bots/{bot_id}")
                if resp.status_code == 200:
                    bot_data = resp.json()
                    if bot_data.get("status") not in ("disconnected",):
                        return bot_id
                ip_to_bot.pop(client_ip, None)
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Bot manager is not available")
        except Exception:
            ip_to_bot.pop(client_ip, None)

    return await _spawn_bot_for_ip(client_ip)


@app.post("/api/chat/send")
async def chat_send(body: ChatSendRequest, request: Request):
    client_ip = get_client_ip(request)
    await require_bot(request)
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    safe_message = _sanitize_chat(body.message)
    try:
        if body.target:
            safe_target = _sanitize_username(body.target)
            if not safe_target:
                raise HTTPException(status_code=400, detail="Invalid target username")
            cmd = f"/tell {safe_target} {safe_message}"
        else:
            cmd = f"/say {safe_message}"
        result = rcon_client.command(cmd)
        print(f"[API] RCON chat: {cmd} -> {result}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] RCON chat error: {e}")
        raise HTTPException(status_code=500, detail=f"RCON error: {str(e)}")


async def teleport_bot(bot_id: str, x: int, y: int, z: int):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BOT_MANAGER_URL}/bots/{bot_id}/execute",
                json={"tool": "teleport", "input": {"x": x, "y": y + 2, "z": z}},
            )
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")


def get_taken_plots() -> set:
    rows = fetchall("SELECT grid_x, grid_z FROM projects")
    return {(r["grid_x"], r["grid_z"]) for r in rows}


def format_project(row: dict) -> dict:
    bounds = get_plot_bounds(row["grid_x"], row["grid_z"])
    world_pos = grid_to_world(row["grid_x"], row["grid_z"])
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "script": row.get("script", ""),
        "creator_ip": row["creator_ip"],
        "grid": {"x": row["grid_x"], "z": row["grid_z"]},
        "world_position": world_pos,
        "plot_bounds": bounds,
        "plot_size": PLOT_SIZE,
        "upvotes": row["upvotes"],
        "downvotes": row["downvotes"],
        "score": row["upvotes"] - row["downvotes"],
        "last_built_at": row["last_built_at"].isoformat() if row.get("last_built_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def format_project_summary(row: dict) -> dict:
    world_pos = grid_to_world(row["grid_x"], row["grid_z"])
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "grid": {"x": row["grid_x"], "z": row["grid_z"]},
        "world_position": world_pos,
        "upvotes": row["upvotes"],
        "downvotes": row["downvotes"],
        "score": row["upvotes"] - row["downvotes"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@app.post("/api/projects")
async def create_project(body: CreateProjectRequest, request: Request):
    bot_id = await require_bot(request)
    client_ip = get_client_ip(request)

    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    if len(body.name) > 100:
        raise HTTPException(status_code=400, detail="Project name must be 100 characters or less")
    if len(body.script) > MAX_SCRIPT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Script must be {MAX_SCRIPT_LENGTH} characters or less")

    import psycopg2
    for attempt in range(5):
        taken = get_taken_plots()
        grid_x, grid_z = get_next_grid_coords(taken)
        try:
            execute(
                "INSERT INTO projects (name, description, script, creator_ip, grid_x, grid_z) VALUES (%s, %s, %s, %s, %s, %s)",
                (body.name.strip(), body.description.strip(), body.script, client_ip, grid_x, grid_z),
            )
            break
        except psycopg2.errors.UniqueViolation:
            if attempt == 4:
                raise HTTPException(status_code=500, detail="Could not assign a plot — please try again")
            continue

    project = fetchone(
        "SELECT * FROM projects WHERE grid_x = %s AND grid_z = %s", (grid_x, grid_z)
    )

    world_pos = grid_to_world(grid_x, grid_z)
    await teleport_bot(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])

    deco_cmds = get_decoration_commands(grid_x, grid_z)
    for cmd in deco_cmds:
        try:
            rcon_client.command(cmd)
        except Exception as e:
            print(f"[API] Decoration error: {e}")

    print(f"[API] Project '{body.name}' created at grid ({grid_x}, {grid_z}) by {client_ip}")
    return format_project(project)


@app.get("/api/projects")
async def list_projects(sort: str = "newest", limit: int = 20, offset: int = 0):
    if sort == "top":
        order = "(upvotes - downvotes) DESC, created_at DESC"
    elif sort == "controversial":
        order = "(upvotes + downvotes) DESC, created_at DESC"
    else:
        order = "created_at DESC"

    rows = fetchall(
        f"SELECT * FROM projects ORDER BY {order} LIMIT %s OFFSET %s",
        (min(limit, 50), offset),
    )
    total = fetchone("SELECT COUNT(*) as count FROM projects")
    return {
        "projects": [format_project_summary(r) for r in rows],
        "total": total["count"] if total else 0,
    }


@app.get("/api/projects/{project_id}")
async def get_project(project_id: int):
    project = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    suggestion_count = fetchone(
        "SELECT COUNT(*) as count FROM suggestions WHERE project_id = %s", (project_id,)
    )
    result = format_project(project)
    result["suggestion_count"] = suggestion_count["count"] if suggestion_count else 0
    return result


@app.post("/api/projects/{project_id}/update")
async def update_project(project_id: int, body: UpdateProjectRequest, request: Request):
    bot_id = await require_bot(request)
    client_ip = get_client_ip(request)

    project = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["creator_ip"] != client_ip:
        raise HTTPException(status_code=403, detail="Only the project creator can update the script")
    if len(body.script) > MAX_SCRIPT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Script must be {MAX_SCRIPT_LENGTH} characters or less")

    execute(
        "UPDATE projects SET script = %s, updated_at = NOW() WHERE id = %s",
        (body.script, project_id),
    )

    world_pos = grid_to_world(project["grid_x"], project["grid_z"])
    await teleport_bot(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])

    updated = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    print(f"[API] Project {project_id} script updated by {client_ip}")
    return format_project(updated)


@app.post("/api/projects/{project_id}/build")
async def build_project(project_id: int, request: Request):
    bot_id = await require_bot(request)
    client_ip = get_client_ip(request)

    project = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["creator_ip"] != client_ip:
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
    await teleport_bot(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])

    buildable = get_plot_bounds(project["grid_x"], project["grid_z"])
    build_origin = get_buildable_origin(project["grid_x"], project["grid_z"])

    sandbox_result = execute_build_script(project["script"], build_origin, buildable)

    if not sandbox_result["success"]:
        return {
            "success": False,
            "error": sandbox_result["error"],
            "block_count": sandbox_result["block_count"],
        }

    async with build_lock:
        execute("UPDATE projects SET last_built_at = NOW() WHERE id = %s", (project_id,))

        clear_cmd = f"/fill {buildable['x1']} {GROUND_Y + 1} {buildable['z1']} {buildable['x2']} {GROUND_Y + 120} {buildable['z2']} minecraft:air"
        try:
            rcon_client.command(clear_cmd)
        except Exception as e:
            print(f"[API] Clear plot error: {e}")

        floor_cmd = f"/fill {buildable['x1']} {GROUND_Y} {buildable['z1']} {buildable['x2']} {GROUND_Y} {buildable['z2']} minecraft:grass_block"
        try:
            rcon_client.command(floor_cmd)
        except Exception as e:
            print(f"[API] Floor error: {e}")

        deco_cmds = get_decoration_commands(project["grid_x"], project["grid_z"])
        for cmd in deco_cmds:
            try:
                rcon_client.command(cmd)
            except Exception as e:
                print(f"[API] Decoration rebuild error: {e}")

        commands_executed = 0
        errors = []
        for cmd in sandbox_result["commands"]:
            try:
                rcon_client.command(cmd)
                commands_executed += 1
            except Exception as e:
                errors.append(f"{cmd}: {str(e)}")
                if len(errors) > 10:
                    break

    print(f"[API] Project {project_id} built: {commands_executed} commands, {sandbox_result['block_count']} blocks")
    return {
        "success": True,
        "commands_executed": commands_executed,
        "block_count": sandbox_result["block_count"],
        "errors": errors if errors else None,
        "buildable_bounds": buildable,
        "world_position": world_pos,
    }


@app.post("/api/projects/{project_id}/suggest")
async def suggest_change(project_id: int, body: SuggestRequest, request: Request):
    await require_bot(request)
    client_ip = get_client_ip(request)

    project = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not body.suggestion or not body.suggestion.strip():
        raise HTTPException(status_code=400, detail="Suggestion cannot be empty")
    if len(body.suggestion) > 2000:
        raise HTTPException(status_code=400, detail="Suggestion must be 2000 characters or less")

    execute(
        "INSERT INTO suggestions (project_id, suggestion, author_ip) VALUES (%s, %s, %s)",
        (project_id, body.suggestion.strip(), client_ip),
    )

    print(f"[API] Suggestion added to project {project_id} by {client_ip}")
    return {"success": True, "project_id": project_id}


@app.get("/api/projects/{project_id}/suggestions")
async def get_suggestions(project_id: int, limit: int = 20, offset: int = 0):
    project = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = fetchall(
        "SELECT * FROM suggestions WHERE project_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (project_id, min(limit, 50), offset),
    )
    total = fetchone(
        "SELECT COUNT(*) as count FROM suggestions WHERE project_id = %s", (project_id,)
    )
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "suggestions": [
            {
                "id": r["id"],
                "suggestion": r["suggestion"],
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            }
            for r in rows
        ],
        "total": total["count"] if total else 0,
    }


@app.post("/api/projects/{project_id}/vote")
async def vote_project(project_id: int, body: VoteRequest, request: Request):
    await require_bot(request)
    client_ip = get_client_ip(request)

    project = fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.direction not in (1, -1):
        raise HTTPException(status_code=400, detail="Direction must be 1 (upvote) or -1 (downvote)")

    existing = fetchone(
        "SELECT * FROM votes WHERE project_id = %s AND voter_ip = %s",
        (project_id, client_ip),
    )

    if existing:
        if existing["direction"] == body.direction:
            execute("DELETE FROM votes WHERE id = %s", (existing["id"],))
            if body.direction == 1:
                execute("UPDATE projects SET upvotes = upvotes - 1 WHERE id = %s", (project_id,))
            else:
                execute("UPDATE projects SET downvotes = downvotes - 1 WHERE id = %s", (project_id,))
            return {"success": True, "action": "removed", "direction": body.direction}
        else:
            execute(
                "UPDATE votes SET direction = %s WHERE id = %s",
                (body.direction, existing["id"]),
            )
            if body.direction == 1:
                execute("UPDATE projects SET upvotes = upvotes + 1, downvotes = downvotes - 1 WHERE id = %s", (project_id,))
            else:
                execute("UPDATE projects SET upvotes = upvotes - 1, downvotes = downvotes + 1 WHERE id = %s", (project_id,))
            return {"success": True, "action": "changed", "direction": body.direction}
    else:
        execute(
            "INSERT INTO votes (project_id, voter_ip, direction) VALUES (%s, %s, %s)",
            (project_id, client_ip, body.direction),
        )
        if body.direction == 1:
            execute("UPDATE projects SET upvotes = upvotes + 1 WHERE id = %s", (project_id,))
        else:
            execute("UPDATE projects SET downvotes = downvotes + 1 WHERE id = %s", (project_id,))
        return {"success": True, "action": "voted", "direction": body.direction}


@app.post("/api/projects/explore")
async def explore_projects(body: ExploreRequest, request: Request):
    bot_id = await require_bot(request)

    if body.mode == "top":
        project = fetchone(
            "SELECT * FROM projects ORDER BY (upvotes - downvotes) DESC, created_at DESC LIMIT 1"
        )
    elif body.mode == "controversial":
        project = fetchone(
            "SELECT * FROM projects ORDER BY (upvotes + downvotes) DESC, created_at DESC LIMIT 1"
        )
    elif body.mode == "random":
        project = fetchone(
            "SELECT * FROM projects ORDER BY RANDOM() LIMIT 1"
        )
    else:
        raise HTTPException(status_code=400, detail="Mode must be 'top', 'random', or 'controversial'")

    if not project:
        raise HTTPException(status_code=404, detail="No projects exist yet")

    world_pos = grid_to_world(project["grid_x"], project["grid_z"])
    await teleport_bot(bot_id, world_pos["x"], world_pos["y"], world_pos["z"])

    print(f"[API] Bot {bot_id} exploring project {project['id']} ({body.mode})")
    return {
        "project": format_project(project),
        "teleported_to": world_pos,
    }


if __name__ == "__main__":
    print(f"[API] Starting MoltCraft API on 0.0.0.0:5000")
    print(f"[API] No auth required — one bot per IP address enforced")
    uvicorn.run(app, host="0.0.0.0", port=5000)
