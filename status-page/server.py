import http.server
import socketserver
import os
import json
import socket
import re
import html

PORT = 5000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MC_LOG_FILE = os.path.join(SCRIPT_DIR, "..", "minecraft-server", "logs", "latest.log")
BORE_ADDRESS_FILE = "/tmp/bore_address.txt"
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "template.html")

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
    except Exception:
        return False


def get_mc_status():
    return check_port(25565)


def get_bore_status():
    try:
        if os.path.exists(BORE_ADDRESS_FILE):
            result = os.popen("pgrep -f 'bore local' 2>/dev/null").read().strip()
            return len(result) > 0
    except Exception:
        pass
    return False


def get_bore_address():
    try:
        if os.path.exists(BORE_ADDRESS_FILE):
            with open(BORE_ADDRESS_FILE, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def get_recent_logs(lines=15):
    try:
        if not os.path.exists(MC_LOG_FILE):
            return "No logs available yet..."
        with open(MC_LOG_FILE, "r") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        filtered = []
        for line in tail:
            line = line.rstrip("\n")
            skip = False
            for pattern in REDACT_PATTERNS:
                if pattern.search(line):
                    skip = True
                    break
            if not skip:
                filtered.append(line)
        return "\n".join(filtered)
    except Exception:
        return "No logs available yet..."


def load_template():
    with open(TEMPLATE_FILE, "r") as f:
        return f.read()


def render_connect_html(bore_address):
    if bore_address:
        return f"""
            <div class="connect-box connect-ready">
                <p>Your server address:</p>
                <code class="server-address">{html.escape(bore_address)}</code>
                <p class="connect-hint">Open Minecraft: <strong>Multiplayer &rarr; Direct Connection</strong><br>Paste the address above and click Join Server</p>
            </div>
        """
    return """
        <div class="connect-box">
            <p>Waiting for tunnel to connect...</p>
            <div class="connect-info">
                The server address will appear here automatically<br>
                once the tunnel is established.
            </div>
        </div>
    """


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

        template = load_template()
        page = template.replace("{{mc_status_text}}", mc_status_text)
        page = page.replace("{{mc_status_color}}", mc_status_color)
        page = page.replace("{{tunnel_status_text}}", tunnel_status_text)
        page = page.replace("{{tunnel_status_color}}", tunnel_status_color)
        page = page.replace("{{connect_html}}", render_connect_html(bore_address))
        page = page.replace("{{logs}}", html.escape(logs))

        self.wfile.write(page.encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), StatusHandler) as httpd:
        print(f"Status page running on port {PORT}")
        httpd.serve_forever()
