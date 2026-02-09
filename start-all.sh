#!/bin/bash
set -e

echo "========================================="
echo "  Minecraft Server Launcher for Replit"
echo "========================================="
echo ""

cleanup() {
    echo ""
    echo "Shutting down..."
    rm -f /tmp/bore_address.txt /tmp/bore_pid.txt
    kill $MC_PID $BORE_PID $STATUS_PID 2>/dev/null
    wait $MC_PID $BORE_PID $STATUS_PID 2>/dev/null
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

echo "[3/3] Starting bore tunnel (TCP tunnel to bore.pub)..."
rm -f /tmp/bore_address.txt /tmp/bore_pid.txt
echo ""
echo "========================================="
echo "  Waiting for Minecraft server to start"
echo "  before opening the tunnel..."
echo "========================================="
echo ""

(
    while ! bash -c "echo >/dev/tcp/127.0.0.1/25565" 2>/dev/null; do
        sleep 2
    done
    echo ""
    echo "========================================="
    echo "  Minecraft server is ready!"
    echo "  Starting bore tunnel..."
    echo "========================================="
    echo ""
    exec "$SCRIPT_DIR/bore" local 25565 --to bore.pub
) 2>&1 | while IFS= read -r line; do
    echo "[bore] $line"
    if echo "$line" | grep -q "listening at"; then
        ADDRESS=$(echo "$line" | grep -oP 'bore\.pub:\d+')
        if [ -n "$ADDRESS" ]; then
            echo "$ADDRESS" > /tmp/bore_address.txt
            echo ""
            echo "========================================="
            echo "  YOUR SERVER ADDRESS: $ADDRESS"
            echo "  Share this with players!"
            echo "  Connect in Minecraft:"
            echo "    Multiplayer -> Direct Connection"
            echo "========================================="
            echo ""
        fi
    fi
done &
BORE_PID=$!

wait $MC_PID $BORE_PID $STATUS_PID
