#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Compiling AI Builder Plugin..."
mkdir -p bin

javac -cp "libs/paper-api.jar:libs/adventure-api.jar:libs/adventure-key.jar:libs/examination-api.jar:libs/bungeecord-chat.jar" \
      -d bin/ \
      src/com/aibuilder/*.java

cp resources/plugin.yml bin/

cd bin
jar cf ../AIBuilder.jar .
cd ..

echo "Built AIBuilder.jar"

if [ -d "../minecraft-server/plugins" ]; then
    cp AIBuilder.jar ../minecraft-server/plugins/
    echo "Installed to minecraft-server/plugins/"
fi
