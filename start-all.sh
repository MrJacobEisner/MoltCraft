#!/bin/bash

echo "========================================="
echo "  MineClaw — Minecraft-as-a-Service"
echo "========================================="
echo ""

cleanup() {
    echo ""
    echo "Shutting down..."
    rm -f /tmp/bore_address.txt /tmp/bore_pid.txt
    kill $MC_PID $BORE_PID $BOT_PID $API_PID 2>/dev/null
    wait $MC_PID $BORE_PID $BOT_PID $API_PID 2>/dev/null
    echo "All processes stopped."
    exit 0
}
trap cleanup SIGTERM SIGINT EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/4] Starting Minecraft server..."
cd "$SCRIPT_DIR/minecraft-server"
bash start.sh &
MC_PID=$!
cd "$SCRIPT_DIR"

echo "[2/4] Starting bore tunnel (TCP tunnel to bore.pub)..."
rm -f /tmp/bore_address.txt /tmp/bore_pid.txt
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

echo "[3/4] Starting Bot Manager (port 3001)..."
(
    while ! bash -c "echo >/dev/tcp/127.0.0.1/25565" 2>/dev/null; do
        sleep 3
    done
    sleep 3
    echo "[BotManager] Minecraft server ready, starting bot manager..."
    cd "$SCRIPT_DIR"
    exec node mineclaw/bot-manager.js
) &
BOT_PID=$!

echo "[4/4] Starting MineClaw API (port 5000)..."
(
    echo "[API] Starting MineClaw API server..."
    cd "$SCRIPT_DIR"
    exec python3 mineclaw/api.py
) &
API_PID=$!

while true; do
    wait -n $MC_PID $BORE_PID $BOT_PID $API_PID 2>/dev/null || sleep 5
done
