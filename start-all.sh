#!/bin/bash
set -e

echo "========================================="
echo "  Minecraft Server Launcher for Replit"
echo "========================================="
echo ""

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $MC_PID $PLAYIT_PID $STATUS_PID 2>/dev/null
    wait $MC_PID $PLAYIT_PID $STATUS_PID 2>/dev/null
    echo "All processes stopped."
    exit 0
}
trap cleanup SIGTERM SIGINT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Starting web status page on port 5000..."
python3 "$SCRIPT_DIR/status-page/server.py" &
STATUS_PID=$!
sleep 1

echo "[2/3] Starting Minecraft server..."
cd "$SCRIPT_DIR/minecraft-server"
bash start.sh &
MC_PID=$!
cd "$SCRIPT_DIR"

echo "[3/3] Starting playit.gg tunnel..."
echo ""
echo "========================================="
echo "  IMPORTANT: Look for the claim URL below"
echo "  Open it in your browser to set up the"
echo "  tunnel and get your server address!"
echo "========================================="
echo ""
"$SCRIPT_DIR/playit-linux-amd64" --stdout &
PLAYIT_PID=$!

wait $MC_PID $PLAYIT_PID $STATUS_PID
