import sys
import os
import socket
import html as html_module
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import httpx
import uvicorn

from rcon import RconClient

API_VERSION = "0.1.0"
BOT_MANAGER_URL = "http://127.0.0.1:3001"
BORE_ADDRESS_FILE = "/tmp/bore_address.txt"

rcon_client = RconClient()

ip_to_bot = {}

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


class SpawnBotRequest(BaseModel):
    username: str = "MoltCraft_Bot"


class ExecuteRequest(BaseModel):
    tool: str
    input: Any


class ExecuteBatchRequest(BaseModel):
    tools: List[ExecuteRequest]


class SetblockRequest(BaseModel):
    x: int
    y: int
    z: int
    block: str


class FillRequest(BaseModel):
    x1: int
    y1: int
    z1: int
    x2: int
    y2: int
    z2: int
    block: str


class FillBatchRequest(BaseModel):
    commands: List[FillRequest]


class ChatSendRequest(BaseModel):
    message: str
    target: Optional[str] = None


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


@app.post("/api/bots")
async def spawn_bot(body: SpawnBotRequest, request: Request):
    client_ip = get_client_ip(request)

    existing_bot_id = get_bot_id_for_ip(client_ip)
    if existing_bot_id:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{BOT_MANAGER_URL}/bots/{existing_bot_id}")
                if resp.status_code == 200:
                    bot_data = resp.json()
                    if bot_data.get("status") not in ("disconnected",):
                        raise HTTPException(
                            status_code=409,
                            detail=f"You already have an active bot (id: {existing_bot_id}). Despawn it first or use it."
                        )
                    else:
                        del ip_to_bot[client_ip]
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Bot manager is not available")
        except HTTPException:
            raise
        except Exception:
            del ip_to_bot[client_ip]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{BOT_MANAGER_URL}/spawn", json={"username": body.username})
            data = resp.json()
            if resp.status_code == 200 and "id" in data:
                ip_to_bot[client_ip] = data["id"]
                print(f"[API] Bot {data['id']} spawned for IP {client_ip}")
            return JSONResponse(content=data, status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def verify_bot_ownership(request: Request, bot_id: str):
    client_ip = get_client_ip(request)
    owned_bot = get_bot_id_for_ip(client_ip)
    if owned_bot != bot_id:
        raise HTTPException(status_code=403, detail="You can only control your own bot")


@app.get("/api/bots")
async def list_bots():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bots/me")
async def get_my_bot(request: Request):
    client_ip = get_client_ip(request)
    bot_id = get_bot_id_for_ip(client_ip)
    if not bot_id:
        raise HTTPException(status_code=404, detail="You don't have a bot. Spawn one first with POST /api/bots")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots/{bot_id}")
            if resp.status_code == 404:
                del ip_to_bot[client_ip]
                raise HTTPException(status_code=404, detail="Your bot was disconnected. Spawn a new one.")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots/{bot_id}")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/bots/{bot_id}")
async def despawn_bot(bot_id: str, request: Request):
    verify_bot_ownership(request, bot_id)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(f"{BOT_MANAGER_URL}/despawn/{bot_id}")
            if resp.status_code == 200:
                client_ip = get_client_ip(request)
                ip_to_bot.pop(client_ip, None)
                print(f"[API] Bot {bot_id} despawned by IP {client_ip}")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bots/{bot_id}/execute")
async def execute_tool(bot_id: str, body: ExecuteRequest, request: Request):
    verify_bot_ownership(request, bot_id)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BOT_MANAGER_URL}/bots/{bot_id}/execute",
                json={"tool": body.tool, "input": body.input},
            )
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bots/{bot_id}/execute-batch")
async def execute_batch(bot_id: str, body: ExecuteBatchRequest, request: Request):
    verify_bot_ownership(request, bot_id)
    results = []
    bot_state = None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for tool_req in body.tools:
                resp = await client.post(
                    f"{BOT_MANAGER_URL}/bots/{bot_id}/execute",
                    json={"tool": tool_req.tool, "input": tool_req.input},
                )
                result = resp.json()
                results.append(result)
                if isinstance(result, dict) and "bot_state" in result:
                    bot_state = result["bot_state"]
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"results": results, "bot_state": bot_state}


@app.get("/api/bots/{bot_id}/observe")
async def observe_bot(bot_id: str, request: Request):
    verify_bot_ownership(request, bot_id)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots/{bot_id}/observe")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def verify_bot_exists(bot_id: str):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots/{bot_id}")
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")


async def get_bot_position(bot_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BOT_MANAGER_URL}/bots/{bot_id}")
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
            data = resp.json()
            pos = data.get("position")
            if not pos:
                raise HTTPException(status_code=400, detail="Bot position not available yet (bot may still be spawning)")
            return pos
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Bot manager is not available")


@app.post("/api/bots/{bot_id}/build/setblock")
async def build_setblock(bot_id: str, body: SetblockRequest, request: Request):
    verify_bot_ownership(request, bot_id)
    pos = await get_bot_position(bot_id)
    abs_x = math.floor(pos["x"] + body.x)
    abs_y = math.floor(pos["y"] + body.y)
    abs_z = math.floor(pos["z"] + body.z)
    cmd = f"/setblock {abs_x} {abs_y} {abs_z} {body.block}"
    try:
        result = rcon_client.command(cmd)
        print(f"[API] RCON setblock: {cmd} -> {result}")
        return {"success": True, "command": cmd, "result": result, "bot_position": pos, "absolute": {"x": abs_x, "y": abs_y, "z": abs_z}}
    except Exception as e:
        print(f"[API] RCON setblock error: {e}")
        raise HTTPException(status_code=500, detail=f"RCON error: {str(e)}")


@app.post("/api/bots/{bot_id}/build/fill")
async def build_fill(bot_id: str, body: FillRequest, request: Request):
    verify_bot_ownership(request, bot_id)
    pos = await get_bot_position(bot_id)
    abs_x1 = math.floor(pos["x"] + body.x1)
    abs_y1 = math.floor(pos["y"] + body.y1)
    abs_z1 = math.floor(pos["z"] + body.z1)
    abs_x2 = math.floor(pos["x"] + body.x2)
    abs_y2 = math.floor(pos["y"] + body.y2)
    abs_z2 = math.floor(pos["z"] + body.z2)
    cmd = f"/fill {abs_x1} {abs_y1} {abs_z1} {abs_x2} {abs_y2} {abs_z2} {body.block}"
    try:
        result = rcon_client.command(cmd)
        print(f"[API] RCON fill: {cmd} -> {result}")
        return {"success": True, "command": cmd, "result": result, "bot_position": pos}
    except Exception as e:
        print(f"[API] RCON fill error: {e}")
        raise HTTPException(status_code=500, detail=f"RCON error: {str(e)}")


@app.post("/api/bots/{bot_id}/build/fill-batch")
async def build_fill_batch(bot_id: str, body: FillBatchRequest, request: Request):
    verify_bot_ownership(request, bot_id)
    pos = await get_bot_position(bot_id)
    results = []
    commands_executed = 0
    for fill_cmd in body.commands:
        abs_x1 = math.floor(pos["x"] + fill_cmd.x1)
        abs_y1 = math.floor(pos["y"] + fill_cmd.y1)
        abs_z1 = math.floor(pos["z"] + fill_cmd.z1)
        abs_x2 = math.floor(pos["x"] + fill_cmd.x2)
        abs_y2 = math.floor(pos["y"] + fill_cmd.y2)
        abs_z2 = math.floor(pos["z"] + fill_cmd.z2)
        cmd = f"/fill {abs_x1} {abs_y1} {abs_z1} {abs_x2} {abs_y2} {abs_z2} {fill_cmd.block}"
        try:
            result = rcon_client.command(cmd)
            print(f"[API] RCON fill-batch: {cmd} -> {result}")
            results.append({"command": cmd, "result": result, "success": True})
            commands_executed += 1
        except Exception as e:
            print(f"[API] RCON fill-batch error: {e}")
            results.append({"command": cmd, "result": str(e), "success": False})
    return {"success": commands_executed == len(body.commands), "commands_executed": commands_executed, "results": results, "bot_position": pos}


def _sanitize_chat(text: str) -> str:
    import re
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r'[^\x20-\x7E]', '', text)
    return text[:500]


def _sanitize_username(name: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '', name)[:16]


@app.post("/api/chat/send")
async def chat_send(body: ChatSendRequest, request: Request):
    client_ip = get_client_ip(request)
    if not get_bot_id_for_ip(client_ip):
        raise HTTPException(status_code=403, detail="You need to spawn a bot first before sending chat messages")
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


if __name__ == "__main__":
    print(f"[API] Starting MoltCraft API on 0.0.0.0:5000")
    print(f"[API] No auth required — one bot per IP address enforced")
    uvicorn.run(app, host="0.0.0.0", port=5000)
