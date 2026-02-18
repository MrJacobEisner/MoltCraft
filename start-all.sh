#!/bin/bash

echo "========================================="
echo "  MoltCraft — Minecraft Server + API"
echo "========================================="
echo ""

cleanup() {
    echo ""
    echo "Shutting down..."
    rm -f /tmp/bore_address.txt
    kill $MC_PID $BORE_PID $BOT_PID $API_PID $BACKUP_PID 2>/dev/null
    wait $MC_PID $BORE_PID $BOT_PID $API_PID $BACKUP_PID 2>/dev/null
    echo "All processes stopped."
    exit 0
}
trap cleanup SIGTERM SIGINT EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- World persistence for production deploys ---
WORLD_DIR="$SCRIPT_DIR/minecraft-server/world"
PERSISTENT_WORLD="/tmp/moltcraft-world-backup"

if [ -n "$REPL_DEPLOYMENT" ]; then
    echo "[World] Production deployment detected"
    if [ -d "$PERSISTENT_WORLD" ]; then
        echo "[World] Restoring production world from persistent storage..."
        rm -rf "$WORLD_DIR"
        cp -a "$PERSISTENT_WORLD" "$WORLD_DIR"
        echo "[World] Production world restored"
    else
        echo "[World] No saved production world found — Minecraft will generate a fresh one"
        rm -rf "$WORLD_DIR"
    fi
fi

echo "[1/4] Starting Minecraft server..."
cd "$SCRIPT_DIR/minecraft-server"
bash start.sh &
MC_PID=$!
cd "$SCRIPT_DIR"

# Periodic world backup to persistent storage (production only)
if [ -n "$REPL_DEPLOYMENT" ]; then
    (
        while ! bash -c "echo >/dev/tcp/127.0.0.1/25565" 2>/dev/null; do
            sleep 5
        done
        sleep 30
        echo "[World] Starting periodic world backup (every 5 minutes)..."
        while true; do
            cp -a "$WORLD_DIR" "${PERSISTENT_WORLD}.tmp" 2>/dev/null
            COPY_OK=$?
            if [ $COPY_OK -eq 0 ] && [ -d "${PERSISTENT_WORLD}.tmp" ]; then
                rm -rf "$PERSISTENT_WORLD"
                mv "${PERSISTENT_WORLD}.tmp" "$PERSISTENT_WORLD"
                echo "[World] Backup saved to persistent storage"
            else
                rm -rf "${PERSISTENT_WORLD}.tmp" 2>/dev/null
                echo "[World] Backup failed, keeping previous backup"
            fi
            sleep 300
        done
    ) &
    BACKUP_PID=$!
fi

echo "[2/4] Starting bore tunnel (TCP tunnel to bore.pub)..."
rm -f /tmp/bore_address.txt
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
    exec node moltcraft/bot-manager.js
) &
BOT_PID=$!

echo "[4/4] Starting MoltCraft API (port 5000)..."
(
    echo "[API] Starting MoltCraft API server..."
    cd "$SCRIPT_DIR"
    exec python3 moltcraft/api.py
) &
API_PID=$!

while true; do
    wait -n $MC_PID $BORE_PID $BOT_PID $API_PID 2>/dev/null || sleep 5
done
