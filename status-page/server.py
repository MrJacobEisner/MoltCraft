import http.server
import socketserver
import os
import subprocess
import json
import socket
import re

PORT = 5000
MC_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "minecraft-server", "logs", "latest.log")
BORE_ADDRESS_FILE = "/tmp/bore_address.txt"

REDACT_PATTERNS = [
    re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
    re.compile(r'logged in with entity id'),
    re.compile(r'lost connection:'),
    re.compile(r'UUID of player'),
]

def check_port(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            return True
    except:
        return False

def get_mc_status():
    return check_port(25565)

def get_bore_status():
    try:
        if os.path.exists("/tmp/bore_address.txt"):
            result = subprocess.run(
                ["pgrep", "-f", "bore local"],
                capture_output=True, text=True, timeout=3
            )
            return result.returncode == 0
    except:
        pass
    return False

def get_bore_address():
    try:
        if os.path.exists(BORE_ADDRESS_FILE):
            with open(BORE_ADDRESS_FILE, "r") as f:
                return f.read().strip()
    except:
        pass
    return ""

def get_recent_logs(lines=15):
    try:
        if os.path.exists(MC_LOG_FILE):
            result = subprocess.run(
                ["tail", f"-{lines}", MC_LOG_FILE],
                capture_output=True, text=True, timeout=5
            )
            filtered = []
            for line in result.stdout.splitlines():
                skip = False
                for pattern in REDACT_PATTERNS:
                    if pattern.search(line):
                        skip = True
                        break
                if not skip:
                    filtered.append(line)
            return "\n".join(filtered)
    except:
        pass
    return "No logs available yet..."

class StatusHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            status = {
                "minecraft_running": get_mc_status(),
                "tunnel_running": get_bore_status(),
                "tunnel_address": get_bore_address(),
                "logs": get_recent_logs()
            }
            self.wfile.write(json.dumps(status).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

        mc_running = get_mc_status()
        tunnel_running = get_bore_status()
        bore_address = get_bore_address()
        logs = get_recent_logs()

        mc_status_text = "Running" if mc_running else "Starting..."
        mc_status_color = "#22c55e" if mc_running else "#f59e0b"
        tunnel_status_text = "Connected" if tunnel_running else "Starting..."
        tunnel_status_color = "#22c55e" if tunnel_running else "#f59e0b"

        if bore_address:
            connect_html = f"""
                <div class="connect-box connect-ready">
                    <p>Your server address:</p>
                    <code class="server-address" id="server-address">{bore_address}</code>
                    <p class="connect-hint">Open Minecraft: <strong>Multiplayer &rarr; Direct Connection</strong><br>Paste the address above and click Join Server</p>
                </div>
            """
        else:
            connect_html = """
                <div class="connect-box">
                    <p>Waiting for tunnel to connect...</p>
                    <div class="connect-info">
                        The server address will appear here automatically<br>
                        once the tunnel is established.
                    </div>
                </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Minecraft Server Status</title>
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
        h1 {{
            font-size: 2rem;
            margin-bottom: 8px;
            color: #fff;
            text-align: center;
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 32px;
            font-size: 0.95rem;
        }}
        .card {{
            background: #16213e;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #2a2a4a;
        }}
        .card h2 {{
            font-size: 1.1rem;
            margin-bottom: 16px;
            color: #aaa;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }}
        .status-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #2a2a4a;
        }}
        .status-row:last-child {{ border-bottom: none; }}
        .status-label {{ font-size: 1rem; }}
        .status-badge {{
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .connect-box {{
            background: #0f3460;
            border: 2px dashed #3a6ea5;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}
        .connect-ready {{
            border: 2px solid #22c55e;
            background: #0f3460;
        }}
        .connect-box p {{ margin-bottom: 8px; color: #aaa; }}
        .connect-info {{
            font-size: 1rem;
            color: #ccc;
            line-height: 1.6;
        }}
        .server-address {{
            display: block;
            font-size: 1.4rem;
            color: #22c55e;
            background: #0d1117;
            padding: 12px 20px;
            border-radius: 8px;
            margin: 12px 0;
            font-weight: bold;
            letter-spacing: 0.5px;
            cursor: pointer;
        }}
        .server-address:hover {{
            background: #161b22;
        }}
        .connect-hint {{
            font-size: 0.9rem;
            color: #888;
            margin-top: 8px;
        }}
        .logs-box {{
            background: #0d1117;
            border-radius: 8px;
            padding: 16px;
            font-family: 'Courier New', monospace;
            font-size: 0.8rem;
            line-height: 1.5;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
            color: #8b949e;
        }}
        .refresh-note {{
            text-align: center;
            color: #555;
            font-size: 0.8rem;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Minecraft Server</h1>
        <p class="subtitle">PaperMC 1.21.11 on Replit &bull; AI Builder Enabled</p>

        <div class="card">
            <h2>Server Status</h2>
            <div class="status-row">
                <span class="status-label">Minecraft Server</span>
                <span class="status-badge" style="background: {mc_status_color}20; color: {mc_status_color};">{mc_status_text}</span>
            </div>
            <div class="status-row">
                <span class="status-label">TCP Tunnel</span>
                <span class="status-badge" style="background: {tunnel_status_color}20; color: {tunnel_status_color};">{tunnel_status_text}</span>
            </div>
        </div>

        <div class="card">
            <h2>Connect to Server</h2>
            <div id="connect-section">
                {connect_html}
            </div>
        </div>

        <div class="card">
            <h2>Server Activity</h2>
            <div class="logs-box" id="logs">{logs}</div>
        </div>

        <p class="refresh-note">Auto-refreshes every 10 seconds</p>
    </div>

    <script>
        async function refresh() {{
            try {{
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('logs').textContent = data.logs;

                const rows = document.querySelectorAll('.status-row');
                const mcBadge = rows[0].querySelector('.status-badge');
                const tunnelBadge = rows[1].querySelector('.status-badge');

                mcBadge.textContent = data.minecraft_running ? 'Running' : 'Starting...';
                mcBadge.style.color = data.minecraft_running ? '#22c55e' : '#f59e0b';
                mcBadge.style.background = data.minecraft_running ? '#22c55e20' : '#f59e0b20';

                tunnelBadge.textContent = data.tunnel_running ? 'Connected' : 'Starting...';
                tunnelBadge.style.color = data.tunnel_running ? '#22c55e' : '#f59e0b';
                tunnelBadge.style.background = data.tunnel_running ? '#22c55e20' : '#f59e0b20';

                const connectSection = document.getElementById('connect-section');
                if (data.tunnel_address) {{
                    connectSection.innerHTML = `
                        <div class="connect-box connect-ready">
                            <p>Your server address:</p>
                            <code class="server-address" id="server-address">${{data.tunnel_address}}</code>
                            <p class="connect-hint">Open Minecraft: <strong>Multiplayer &rarr; Direct Connection</strong><br>Paste the address above and click Join Server</p>
                        </div>
                    `;
                }} else {{
                    connectSection.innerHTML = `
                        <div class="connect-box">
                            <p>Waiting for tunnel to connect...</p>
                            <div class="connect-info">
                                The server address will appear here automatically<br>
                                once the tunnel is established.
                            </div>
                        </div>
                    `;
                }}
            }} catch(e) {{}}
        }}
        setInterval(refresh, 10000);
    </script>
</body>
</html>"""
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), StatusHandler) as httpd:
        print(f"Status page running on port {PORT}")
        httpd.serve_forever()
