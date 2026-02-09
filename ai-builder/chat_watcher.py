import os
import sys
import time
import re
import ast
import signal
import traceback
import json
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon_client import RconClient
from mc_builder import MinecraftBuilder
from ai_providers import parse_command, resolve_model, generate_build_script, get_available_models_text

VALID_PROVIDERS = {"claude", "openai", "gemini", "openrouter"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.environ.get("MC_LOG_FILE", os.path.join(SCRIPT_DIR, "..", "minecraft-server", "logs", "latest.log"))
STRUCTURES_DIR = os.path.join(SCRIPT_DIR, "..", "minecraft-server", "world", "datapacks", "ai-builder", "data", "ai", "structures")

MAX_CODE_LENGTH = 50000
EXEC_TIMEOUT = 60

ALLOWED_IMPORTS = {"math"}

SAFE_BUILDER_ATTRS = {
    "place_block", "fill", "fill_hollow", "fill_outline", "fill_replace",
    "wall", "floor", "box", "cylinder", "sphere", "dome",
    "line", "circle", "arc", "spiral", "pyramid", "stairs",
    "clear_area", "get_block_count",
}

SAFE_MATH_ATTRS = {
    "pi", "e", "tau", "inf",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sqrt", "ceil", "floor", "log", "log2", "log10", "exp",
    "radians", "degrees", "hypot", "pow", "fabs",
    "gcd", "factorial", "comb", "perm",
}

ALLOWED_ATTR_NAMES = SAFE_BUILDER_ATTRS | SAFE_MATH_ATTRS | {
    "append", "extend", "insert", "pop", "remove", "sort", "reverse",
    "keys", "values", "items", "get", "update",
    "upper", "lower", "strip", "split", "join", "replace", "format",
    "startswith", "endswith",
    "real", "imag",
}

BLOCKED_ATTR_PREFIXES = {"__", "_"}


class CodeSecurityError(Exception):
    pass


class ExecTimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise ExecTimeoutError(f"Build script exceeded {EXEC_TIMEOUT}s time limit")


class SafetyValidator(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name not in ALLOWED_IMPORTS:
                self.errors.append(f"Import not allowed: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module not in ALLOWED_IMPORTS:
            self.errors.append(f"Import not allowed: {node.module}")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        attr = node.attr
        if any(attr.startswith(p) for p in BLOCKED_ATTR_PREFIXES):
            self.errors.append(f"Blocked attribute access: {attr}")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            blocked_funcs = {
                "eval", "exec", "compile", "execfile",
                "__import__", "open", "input", "breakpoint",
                "exit", "quit", "help", "dir", "type",
                "getattr", "setattr", "delattr", "hasattr",
                "globals", "locals", "vars", "id", "hash",
                "memoryview", "bytearray", "bytes", "classmethod",
                "staticmethod", "property", "super", "object",
            }
            if node.func.id in blocked_funcs:
                self.errors.append(f"Blocked function call: {node.func.id}")
        self.generic_visit(node)

    def visit_While(self, node):
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self.errors.append("Infinite loop detected: while True")
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.errors.append("Lambda functions not allowed")
        self.generic_visit(node)

    def visit_Global(self, node):
        self.errors.append("Global statements not allowed")
        self.generic_visit(node)

    def visit_Nonlocal(self, node):
        self.errors.append("Nonlocal statements not allowed")
        self.generic_visit(node)

    def visit_Delete(self, node):
        self.errors.append("Delete statements not allowed")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.errors.append("Class definitions not allowed")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.errors.append("Async functions not allowed")
        self.generic_visit(node)

    def visit_Await(self, node):
        self.errors.append("Await not allowed")
        self.generic_visit(node)

    def visit_Yield(self, node):
        self.errors.append("Yield not allowed")
        self.generic_visit(node)

    def visit_YieldFrom(self, node):
        self.errors.append("Yield not allowed")
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.errors.append("Raise not allowed")
        self.generic_visit(node)

    def visit_Try(self, node):
        self.generic_visit(node)

    def visit_With(self, node):
        self.errors.append("With statements not allowed")
        self.generic_visit(node)


def validate_code_safety(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    validator = SafetyValidator()
    validator.visit(tree)

    if validator.errors:
        return False, "; ".join(validator.errors[:3])

    return True, "OK"


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
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "builder.", "for ", "bx", "by", "bz")):
            in_code = True
        if in_code:
            code_lines.append(line)
    if code_lines:
        return "\n".join(code_lines)
    return response


def execute_build(rcon, code, player_name):
    if len(code) > MAX_CODE_LENGTH:
        rcon.command(f'tellraw {player_name} {json.dumps({"text": "Generated code too long, aborting.", "color": "red"})}')
        return 0

    is_safe, reason = validate_code_safety(code)
    if not is_safe:
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Code rejected: {reason}", "color": "red"})}')
        print(f"[AI Builder] Code rejected: {reason}")
        return 0

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
            rcon.command(f'tellraw {player_name} {json.dumps({"text": "Could not get your position, building at spawn", "color": "yellow"})}')
    except Exception:
        px, py, pz = 0, 64, 0

    import math as _math

    _allowed_modules = {"math": _math}
    def _safe_import(name, *args, **kwargs):
        if name in _allowed_modules:
            return _allowed_modules[name]
        raise ImportError(f"Import not allowed: {name}")

    exec_globals = {
        "__builtins__": {"__import__": _safe_import},
        "builder": builder,
        "px": px, "py": py, "pz": pz,
        "math": _math,
        "range": range,
        "int": int,
        "float": float,
        "round": round,
        "abs": abs,
        "min": min,
        "max": max,
        "len": len,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "str": str,
        "bool": bool,
        "enumerate": enumerate,
        "zip": zip,
        "sorted": sorted,
        "reversed": reversed,
        "sum": sum,
        "any": any,
        "all": all,
        "map": map,
        "filter": filter,
        "isinstance": isinstance,
        "True": True,
        "False": False,
        "None": None,
        "print": lambda *a, **kw: None,
    }

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(EXEC_TIMEOUT)
    try:
        exec(code, exec_globals)
    except MinecraftBuilder.BuildLimitError as e:
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Build too large: {e}", "color": "red"})}')
        print(f"[AI Builder] Block limit hit: {e}")
    except ExecTimeoutError as e:
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Build timed out ({EXEC_TIMEOUT}s limit). Simplify your request.", "color": "red"})}')
        print(f"[AI Builder] Timeout: {e}")
    except Exception as e:
        error_msg = str(e)[:150]
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Build script error: {error_msg}", "color": "red"})}')
        print(f"[AI Builder] Exec error: {traceback.format_exc()}")
        return 0
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    block_count = builder.get_block_count()
    if block_count == 0:
        rcon.command(f'tellraw {player_name} {json.dumps({"text": "AI generated no blocks.", "color": "red"})}')
        return 0

    os.makedirs(STRUCTURES_DIR, exist_ok=True)

    bounds = builder.get_bounds()
    if bounds and bounds[0] is not None:
        min_coords = bounds[0]
        place_x, place_y, place_z = min_coords.x, min_coords.y, min_coords.z
    else:
        place_x, place_y, place_z = px + 3, py, pz + 3

    build_id = f"build_{uuid.uuid4().hex[:8]}"
    nbt_path = os.path.join(STRUCTURES_DIR, f"{build_id}.nbt")

    try:
        builder.save(nbt_path)
        print(f"[AI Builder] Saved NBT structure: {nbt_path} ({block_count} blocks)")
    except Exception as e:
        error_msg = str(e)[:150]
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Failed to save structure: {error_msg}", "color": "red"})}')
        print(f"[AI Builder] NBT save error: {traceback.format_exc()}")
        return 0

    try:
        reload_result = rcon.command("reload")
        print(f"[AI Builder] Reload: {reload_result}")
        time.sleep(1)
    except Exception as e:
        print(f"[AI Builder] Reload warning: {e}")
        time.sleep(1)

    rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Placing {block_count} blocks instantly...", "color": "aqua"})}')

    try:
        place_cmd = f"place template ai:{build_id} {place_x} {place_y} {place_z}"
        result = rcon.command(place_cmd)
        print(f"[AI Builder] Place result: {result}")

        if "error" in result.lower() or "unknown" in result.lower() or "invalid" in result.lower():
            rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Place failed: {result}", "color": "red"})}')
            print(f"[AI Builder] Place command failed: {result}")
            return 0
    except Exception as e:
        error_msg = str(e)[:150]
        rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Place failed: {error_msg}", "color": "red"})}')
        print(f"[AI Builder] Place error: {traceback.format_exc()}")
        return 0

    try:
        if os.path.exists(nbt_path):
            os.remove(nbt_path)
    except Exception:
        pass

    return block_count


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
        rcon.command(f'tellraw {player_name} {json.dumps(line)}')


def tell_models(rcon, player_name):
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


def ensure_rcon(rcon):
    if not rcon.sock:
        rcon.connect()
    return rcon


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

    chat_pattern = re.compile(r'\[.*?INFO\].*?:\s*<(\w+)>\s*(.*)')

    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)
        print("[AI Builder] Watching for chat commands...")

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            chat_match = chat_pattern.search(line)
            if not chat_match:
                continue

            player_name = chat_match.group(1)
            message = chat_match.group(2).strip()

            if not message.startswith("!"):
                continue

            try:
                ensure_rcon(rcon)
            except Exception as e:
                print(f"[AI Builder] RCON reconnect failed: {e}")
                time.sleep(2)
                continue

            if message.lower() == "!help":
                try:
                    tell_help(rcon, player_name)
                except Exception as e:
                    print(f"[AI Builder] Error sending help: {e}")
                continue

            if message.lower() == "!models":
                try:
                    tell_models(rcon, player_name)
                except Exception as e:
                    print(f"[AI Builder] Error sending models: {e}")
                continue

            provider, model_alias, prompt = parse_command(message)

            if not provider or provider not in VALID_PROVIDERS:
                continue

            if not prompt:
                try:
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Usage: !{provider} <what to build>", "color": "yellow"})}')
                except Exception:
                    pass
                continue

            model = resolve_model(provider, model_alias)
            if not model:
                try:
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Unknown model: {model_alias}", "color": "red"})}')
                except Exception:
                    pass
                continue

            model_display = f"{provider}/{model}"
            if model_alias:
                model_display = f"{provider}:{model_alias} ({model})"

            print(f"[AI Builder] {player_name} requested: {prompt}")
            print(f"[AI Builder] Using: {model_display}")

            try:
                rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Generating build with {model_display}...", "color": "gold"})}')
                rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Prompt: {prompt}", "color": "gray"})}')

                response = generate_build_script(provider, model, prompt)
                code = extract_code(response)

                if not code:
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": "AI returned no usable code.", "color": "red"})}')
                    continue

                print(f"[AI Builder] Generated code:\n{code[:500]}...")

                block_count = execute_build(rcon, code, player_name)

                if block_count > 0:
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Done! Placed {block_count} blocks instantly using {model_display}.", "color": "green"})}')
                    print(f"[AI Builder] Build complete: {block_count} blocks (NBT)")

            except Exception as e:
                error_msg = str(e)[:200]
                print(f"[AI Builder] Error: {traceback.format_exc()}")
                try:
                    rcon.command(f'tellraw {player_name} {json.dumps({"text": f"Build failed: {error_msg}", "color": "red"})}')
                except Exception:
                    pass
                try:
                    rcon.disconnect()
                    rcon.connect()
                except Exception:
                    pass


if __name__ == "__main__":
    watch_chat()
