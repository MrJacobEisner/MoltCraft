import os
import sys
import time
import re
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon_client import RconClient
from mc_builder import MinecraftBuilder
from ai_providers import parse_command, resolve_model, generate_build_script, get_available_models_text

VALID_PROVIDERS = {"claude", "openai", "gemini", "openrouter"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.environ.get("MC_LOG_FILE", os.path.join(SCRIPT_DIR, "..", "minecraft-server", "logs", "latest.log"))


def extract_code(response):
    patterns = [
        r"```python\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
    lines = response.strip().split("\n")
    code_lines = []
    in_code = False
    for line in lines:
        if line.strip().startswith("import ") or line.strip().startswith("from ") or line.strip().startswith("builder.") or line.strip().startswith("for ") or line.strip().startswith("bx") or line.strip().startswith("by") or line.strip().startswith("bz"):
            in_code = True
        if in_code:
            code_lines.append(line)
    if code_lines:
        return "\n".join(code_lines)
    return response


def execute_build(rcon, code, player_name):
    builder = MinecraftBuilder()

    try:
        player_pos = rcon.command(f"data get entity {player_name} Pos")
        pos_match = re.search(r'\[(-?[\d.]+)d,\s*(-?[\d.]+)d,\s*(-?[\d.]+)d\]', player_pos)
        if pos_match:
            px = int(float(pos_match.group(1)))
            py = int(float(pos_match.group(2)))
            pz = int(float(pos_match.group(3)))
        else:
            px, py, pz = 0, 64, 0
            rcon.command(f'tellraw {player_name} {{"text":"Could not get your position, building at spawn","color":"yellow"}}')
    except Exception:
        px, py, pz = 0, 64, 0

    exec_globals = {
        "builder": builder,
        "px": px, "py": py, "pz": pz,
        "math": __import__("math"),
    }

    exec(code, exec_globals)

    commands = builder.get_commands()
    if not commands:
        rcon.command(f'tellraw {player_name} {{"text":"AI generated no build commands.","color":"red"}}')
        return 0

    total = len(commands)
    rcon.command(f'tellraw {player_name} {{"text":"Building {total} blocks... please wait!","color":"aqua"}}')

    batch_size = 50
    for i in range(0, total, batch_size):
        batch = commands[i:i + batch_size]
        rcon.send_commands(batch, delay=0.02)
        progress = min(i + batch_size, total)
        if total > 100 and progress % 200 == 0:
            pct = int(progress / total * 100)
            rcon.command(f'tellraw {player_name} {{"text":"Progress: {pct}% ({progress}/{total})","color":"gray"}}')

    return total


def tell_help(rcon, player_name):
    help_lines = [
        {"text": "=== AI Builder Commands ===", "color": "gold", "bold": True},
        {"text": ""},
        {"text": "!claude <prompt>", "color": "green"},
        {"text": " - Build with Claude Opus 4.5", "color": "gray"},
        {"text": "!openai <prompt>", "color": "green"},
        {"text": " - Build with GPT-5.2", "color": "gray"},
        {"text": "!gemini <prompt>", "color": "green"},
        {"text": " - Build with Gemini 3 Pro", "color": "gray"},
        {"text": "!openrouter:deepseek <prompt>", "color": "green"},
        {"text": " - Build with DeepSeek R1", "color": "gray"},
        {"text": ""},
        {"text": "Add :model to specify: !claude:haiku, !openai:o4-mini, !gemini:flash", "color": "yellow"},
        {"text": "Type !models for full model list", "color": "yellow"},
    ]
    for line in help_lines:
        import json
        rcon.command(f'tellraw {player_name} {json.dumps(line)}')


def tell_models(rcon, player_name):
    import json
    model_groups = [
        ("Claude", "light_purple", [
            ("!claude", "Opus 4.5 (default)"),
            ("!claude:sonnet", "Sonnet 4.5"),
            ("!claude:haiku", "Haiku 4.5"),
        ]),
        ("OpenAI", "green", [
            ("!openai", "GPT-5.2 (default)"),
            ("!openai:gpt-5.1", "GPT-5.1"),
            ("!openai:gpt5-mini", "GPT-5 Mini"),
            ("!openai:o4-mini", "o4-mini"),
        ]),
        ("Gemini", "blue", [
            ("!gemini", "Gemini 3 Pro (default)"),
            ("!gemini:flash", "Gemini 3 Flash"),
            ("!gemini:2.5-pro", "Gemini 2.5 Pro"),
        ]),
        ("OpenRouter", "aqua", [
            ("!openrouter:deepseek", "DeepSeek R1"),
            ("!openrouter:llama", "Llama 3"),
            ("!openrouter:qwen", "Qwen 3"),
            ("!openrouter:mistral", "Mistral Nemo"),
        ]),
    ]
    rcon.command(f'tellraw {player_name} {json.dumps({"text": "=== Available Models ===", "color": "gold", "bold": True})}')
    for group_name, color, models in model_groups:
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"  {group_name}:", "color": color, "bold": True})}')
        for cmd, desc in models:
            rcon.command(f'tellraw {player_name} {json.dumps({"text": f"    {cmd} - {desc}", "color": "gray"})}')


def watch_chat():
    print("[AI Builder] Starting chat watcher...")
    print(f"[AI Builder] Watching log file: {LOG_FILE}")

    rcon = RconClient()
    try:
        rcon.connect()
        print("[AI Builder] Connected to RCON")
    except Exception as e:
        print(f"[AI Builder] RCON connection failed: {e}")
        print("[AI Builder] Will retry on first command...")

    while not os.path.exists(LOG_FILE):
        print(f"[AI Builder] Waiting for log file to appear...")
        time.sleep(5)

    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)
        print("[AI Builder] Watching for chat commands...")

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            chat_match = re.search(r'\[Server thread/INFO\].*?:\s*<(\w+)>\s*(.*)', line)
            if not chat_match:
                continue

            player_name = chat_match.group(1)
            message = chat_match.group(2).strip()

            if not message.startswith("!"):
                continue

            if message.lower() == "!help":
                try:
                    if not rcon.sock:
                        rcon.connect()
                    tell_help(rcon, player_name)
                except Exception as e:
                    print(f"[AI Builder] Error sending help: {e}")
                continue

            if message.lower() == "!models":
                try:
                    if not rcon.sock:
                        rcon.connect()
                    tell_models(rcon, player_name)
                except Exception as e:
                    print(f"[AI Builder] Error sending models: {e}")
                continue

            provider, model_alias, prompt = parse_command(message)

            if not provider or provider not in VALID_PROVIDERS:
                continue

            if not prompt:
                try:
                    if not rcon.sock:
                        rcon.connect()
                    rcon.command(f'tellraw {player_name} {{"text":"Usage: !{provider} <what to build>","color":"yellow"}}')
                except:
                    pass
                continue

            model = resolve_model(provider, model_alias)
            if not model:
                continue

            model_display = f"{provider}/{model}"
            if model_alias:
                model_display = f"{provider}:{model_alias} ({model})"

            print(f"[AI Builder] {player_name} requested: {prompt}")
            print(f"[AI Builder] Using: {model_display}")

            try:
                if not rcon.sock:
                    rcon.connect()

                import json
                rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Generating build with {model_display}...", "color": "gold"})}')
                rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Prompt: {prompt}", "color": "gray"})}')

                response = generate_build_script(provider, model, prompt)
                code = extract_code(response)

                if not code:
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": "AI returned no usable code.", "color": "red"})}')
                    continue

                print(f"[AI Builder] Generated code:\n{code[:500]}...")

                block_count = execute_build(rcon, code, player_name)

                rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Done! Placed {block_count} blocks using {model_display}.", "color": "green"})}')
                print(f"[AI Builder] Build complete: {block_count} blocks")

            except Exception as e:
                error_msg = str(e)[:200]
                print(f"[AI Builder] Error: {traceback.format_exc()}")
                try:
                    import json
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Build failed: {error_msg}", "color": "red"})}')
                except:
                    pass
                try:
                    rcon.disconnect()
                    rcon.connect()
                except:
                    pass


if __name__ == "__main__":
    watch_chat()
