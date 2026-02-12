import os
import sys
import time
import re
import ast
import signal
import traceback
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon_client import RconClient
from mc_builder import MinecraftBuilder
from ai_providers import resolve_model, generate_build_script, calculate_cost, build_retry_prompt
from boss_bar import BossBarManager
from build_book import give_build_book

VALID_PROVIDERS = {"claude", "openai", "gemini", "deepseek", "kimi", "grok", "glm"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.environ.get("MC_LOG_FILE", os.path.join(SCRIPT_DIR, "..", "minecraft-server", "logs", "latest.log"))
PLUGIN_QUEUE_DIR = os.path.join(SCRIPT_DIR, "..", "minecraft-server", "plugins", "AIBuilder", "queue")

MAX_CODE_LENGTH = 50000
EXEC_TIMEOUT = 60
MAX_AI_RETRIES = 3
BATCH_SIZE = 50
BATCH_DELAY = 0.05

ALLOWED_IMPORTS = {"math", "random", "itertools", "functools", "collections", "string", "colorsys", "copy"}

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
            explanation = response[:match.start()].strip()
            explanation = re.sub(r'[#*_`~>]', '', explanation).strip()
            return match.group(1).strip(), explanation
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
        return "\n".join(code_lines), ""
    return response, ""


def _tell(rcon, player_name, components):
    rcon.command(f'tellraw {player_name} {json.dumps(components)}')


def _tell_ai(rcon, player_name, text, color="yellow"):
    _tell(rcon, player_name, [
        {"text": "[AI] ", "color": "gold", "bold": True},
        {"text": text, "color": color, "bold": False}
    ])


def _get_player_position(rcon, player_name):
    try:
        player_pos = rcon.command(f"data get entity {player_name} Pos")
        pos_match = re.search(r'\[(-?[\d.]+)d,\s*(-?[\d.]+)d,\s*(-?[\d.]+)d\]', player_pos)
        if pos_match:
            return (
                int(float(pos_match.group(1))),
                int(float(pos_match.group(2))),
                int(float(pos_match.group(3)))
            )
    except Exception:
        pass
    _tell(rcon, player_name, {"text": "Could not get your position, building at spawn", "color": "yellow"})
    return 0, 64, 0


def _build_sandbox_globals(builder):
    import math as _math
    import random as _random
    import itertools as _itertools
    import functools as _functools
    import collections as _collections
    import string as _string
    import colorsys as _colorsys
    import copy as _copy

    allowed_modules = {
        "math": _math, "random": _random, "itertools": _itertools,
        "functools": _functools, "collections": _collections,
        "string": _string, "colorsys": _colorsys, "copy": _copy,
    }

    def safe_import(name, *args, **kwargs):
        if name in allowed_modules:
            return allowed_modules[name]
        raise ImportError(f"Import not allowed: {name}")

    return {
        "__builtins__": {"__import__": safe_import},
        "builder": builder,
        "math": _math, "random": _random,
        "range": range, "int": int, "float": float, "round": round,
        "abs": abs, "min": min, "max": max, "len": len,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "str": str, "bool": bool,
        "enumerate": enumerate, "zip": zip,
        "sorted": sorted, "reversed": reversed,
        "sum": sum, "any": any, "all": all,
        "map": map, "filter": filter, "isinstance": isinstance,
        "True": True, "False": False, "None": None,
        "print": lambda *a, **kw: None,
    }


def _execute_code_sandboxed(code, builder):
    exec_globals = _build_sandbox_globals(builder)
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(EXEC_TIMEOUT)
    try:
        exec(code, exec_globals)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _place_commands(rcon, player_name, commands):
    errors = 0
    for i, cmd in enumerate(commands):
        try:
            result = rcon.command(cmd)
            if result and ("error" in result.lower() or "unknown" in result.lower()):
                errors += 1
                if errors <= 3:
                    print(f"[AI Builder] Command error: {cmd[:80]} -> {result}")
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"[AI Builder] RCON error on command: {cmd[:80]} -> {e}")
            try:
                rcon.reconnect()
            except Exception:
                pass

        if i > 0 and i % BATCH_SIZE == 0:
            time.sleep(BATCH_DELAY)

    return errors


def execute_build(rcon, code, player_name, bar=None):
    if len(code) > MAX_CODE_LENGTH:
        return {"block_count": 0, "error": "Generated code too long, aborting."}

    is_safe, reason = validate_code_safety(code)
    if not is_safe:
        print(f"[AI Builder] Code rejected: {reason}")
        return {"block_count": 0, "error": f"Code safety check failed: {reason}"}

    builder = MinecraftBuilder()
    px, py, pz = _get_player_position(rcon, player_name)
    offset = (px + 3, py, pz + 3)

    try:
        _execute_code_sandboxed(code, builder)
    except ExecTimeoutError as e:
        print(f"[AI Builder] Timeout: {e}")
        return {"block_count": 0, "error": f"Build timed out ({EXEC_TIMEOUT}s limit). Simplify your request."}
    except Exception as e:
        error_msg = str(e)[:300]
        print(f"[AI Builder] Exec error: {traceback.format_exc()}")
        return {"block_count": 0, "error": f"Python error: {error_msg}"}

    block_count = builder.get_block_count()
    if block_count == 0:
        return {"block_count": 0, "error": "Code executed but generated no blocks. Make sure to call builder methods."}

    if bar:
        bar.set_phase(f"Placing {block_count} blocks...")

    commands = builder.generate_commands(offset=offset)
    cmd_count = len(commands)
    print(f"[AI Builder] {block_count} blocks optimized into {cmd_count} commands")

    errors = _place_commands(rcon, player_name, commands)

    if cmd_count > 0 and errors > cmd_count * 0.5:
        return {"block_count": 0, "error": f"Too many placement errors ({errors}/{cmd_count} commands failed)"}

    return {"block_count": block_count, "error": None, "coords": (px, py, pz), "cmd_count": cmd_count}


def tell_help(rcon, player_name):
    help_lines = [
        {"text": "=== AI Builder Commands ===", "color": "gold", "bold": True},
        {"text": ""},
        {"text": "/claude <prompt>", "color": "green"},
        {"text": " - Build with Claude Opus 4.6", "color": "gray"},
        {"text": "/openai <prompt>", "color": "green"},
        {"text": " - Build with GPT-5.2", "color": "gray"},
        {"text": "/gemini <prompt>", "color": "green"},
        {"text": " - Build with Gemini 3 Pro", "color": "gray"},
        {"text": "/deepseek <prompt>", "color": "green"},
        {"text": " - Build with DeepSeek V3.2", "color": "gray"},
        {"text": "/kimi <prompt>", "color": "green"},
        {"text": " - Build with Kimi K2.5", "color": "gray"},
        {"text": "/grok <prompt>", "color": "green"},
        {"text": " - Build with Grok 4", "color": "gray"},
        {"text": "/glm <prompt>", "color": "green"},
        {"text": " - Build with GLM 5", "color": "gray"},
        {"text": ""},
        {"text": "Specify model: /claude :haiku, /openai :o4-mini, /gemini :flash", "color": "yellow"},
        {"text": "Type /models for full model list", "color": "yellow"},
    ]
    for line in help_lines:
        _tell(rcon, player_name, line)


def tell_models(rcon, player_name):
    model_groups = [
        ("Claude", "light_purple", [
            ("/claude", "Opus 4.6 (default)"),
            ("/claude :opus4.5", "Opus 4.5"),
            ("/claude :sonnet", "Sonnet 4.5"),
            ("/claude :haiku", "Haiku 4.5"),
        ]),
        ("OpenAI", "green", [
            ("/openai", "GPT-5.2 (default)"),
            ("/openai :gpt-5.1", "GPT-5.1"),
            ("/openai :gpt5-mini", "GPT-5 Mini"),
            ("/openai :o4-mini", "o4-mini"),
        ]),
        ("Gemini", "blue", [
            ("/gemini", "Gemini 3 Pro (default)"),
            ("/gemini :flash", "Gemini 3 Flash"),
            ("/gemini :2.5-pro", "Gemini 2.5 Pro"),
        ]),
        ("DeepSeek", "aqua", [
            ("/deepseek", "DeepSeek V3.2 (default)"),
            ("/deepseek :r1", "DeepSeek R1"),
        ]),
        ("Kimi", "aqua", [
            ("/kimi", "Kimi K2.5 (default)"),
        ]),
        ("Grok", "aqua", [
            ("/grok", "Grok 4 (default)"),
        ]),
        ("GLM", "aqua", [
            ("/glm", "GLM 5 (default)"),
        ]),
    ]
    _tell(rcon, player_name, {"text": "=== Available Models ===", "color": "gold", "bold": True})
    for group_name, color, models in model_groups:
        _tell(rcon, player_name, {"text": f"  {group_name}:", "color": color, "bold": True})
        for cmd, desc in models:
            _tell(rcon, player_name, {"text": f"    {cmd} - {desc}", "color": "gray"})


def _parse_provider_and_model(command_str):
    if ":" in command_str:
        provider = command_str.split(":")[0]
        model_alias = command_str.split(":")[1]
    else:
        provider = command_str
        model_alias = None
    return provider, model_alias


def _generate_with_retries(rcon, player_name, provider, model, prompt, bar=None):
    current_prompt = prompt
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    final_attempt = 1
    final_code = ""
    build_result = None

    for attempt in range(1, MAX_AI_RETRIES + 1):
        final_attempt = attempt
        if attempt > 1:
            if bar:
                bar.set_phase(f"Retry {attempt}/{MAX_AI_RETRIES}...")

        gen_start = time.time()
        result = generate_build_script(provider, model, current_prompt)
        gen_time = time.time() - gen_start

        response_text = result["text"]
        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_cost += calculate_cost(model, input_tokens, output_tokens)

        if bar:
            bar.set_phase("Building...")

        code, explanation = extract_code(response_text)

        if not code:
            if attempt < MAX_AI_RETRIES:
                current_prompt = build_retry_prompt(prompt, "(no code generated)", "AI returned no usable Python code block. You MUST output a Python code block with builder calls.")
                continue
            _tell_ai(rcon, player_name, "Build failed — no usable code generated.", "red")
            return None

        final_code = code
        print(f"[AI Builder] Generated code (attempt {attempt}):\n{code[:500]}...")

        if bar:
            bar.set_phase("Placing blocks...")

        build_result = execute_build(rcon, code, player_name, bar=bar)
        block_count = build_result["block_count"]
        error = build_result.get("error")

        if block_count > 0:
            break

        error = error or "Unknown error (no blocks placed)"
        print(f"[AI Builder] Build failed (attempt {attempt}/{MAX_AI_RETRIES}): {error}")

        if attempt < MAX_AI_RETRIES:
            current_prompt = build_retry_prompt(prompt, code, error)
        else:
            _tell_ai(rcon, player_name, f"Build failed: {error[:150]}", "red")

    if not build_result or build_result["block_count"] <= 0:
        return None

    return {
        "block_count": build_result["block_count"],
        "cmd_count": build_result.get("cmd_count", 0),
        "coords": build_result.get("coords", (0, 64, 0)),
        "code": final_code,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "cost": total_cost,
        "attempts": final_attempt,
    }


def _report_build_stats(rcon, player_name, model, stats, total_time):
    block_count = stats["block_count"]
    total_cost = stats["cost"]
    attempts = stats["attempts"]

    cost_str = f"${total_cost:.4f}" if total_cost < 0.01 else f"${total_cost:.3f}"
    attempt_note = f" ({attempts} attempts)" if attempts > 1 else ""

    _tell(rcon, player_name, [
        {"text": "[AI] ", "color": "gold", "bold": True},
        {"text": "Done! ", "color": "green"},
        {"text": f"{block_count:,} blocks", "color": "white"},
        {"text": f" | {total_time:.1f}s | {cost_str}{attempt_note}", "color": "gray"},
    ])

    total_tokens = stats["input_tokens"] + stats["output_tokens"]
    print(f"[AI Builder] Build complete: {block_count} blocks | {total_tokens} tokens | {cost_str} | {total_time:.1f}s | attempts: {attempts}")


def process_command(rcon, player_name, command_str, prompt):
    if command_str.lower() in ("aihelp", "help"):
        try:
            tell_help(rcon, player_name)
        except Exception as e:
            print(f"[AI Builder] Error sending help: {e}")
        return

    if command_str.lower() == "models":
        try:
            tell_models(rcon, player_name)
        except Exception as e:
            print(f"[AI Builder] Error sending models: {e}")
        return

    provider, model_alias = _parse_provider_and_model(command_str)

    if provider not in VALID_PROVIDERS:
        return

    if not prompt:
        try:
            _tell(rcon, player_name, {"text": f"Usage: /{provider} <what to build>", "color": "yellow"})
        except Exception:
            pass
        return

    model = resolve_model(provider, model_alias)
    if not model:
        try:
            _tell(rcon, player_name, {"text": f"Unknown model: {model_alias}", "color": "red"})
        except Exception:
            pass
        return

    model_display = f"{provider}/{model}"
    if model_alias:
        model_display = f"{provider}:{model_alias} ({model})"

    print(f"[AI Builder] {player_name} requested: {prompt}")
    print(f"[AI Builder] Using: {model_display}")

    bar = BossBarManager(rcon, player_name)
    try:
        bar.start(f"{model_display}: {prompt[:40]}...")

        _tell_ai(rcon, player_name, f"Building with {model_display}...")

        start_time = time.time()
        stats = _generate_with_retries(rcon, player_name, provider, model, prompt, bar=bar)
        total_time = time.time() - start_time

        if stats:
            bar.complete("Build complete!")
            _report_build_stats(rcon, player_name, model, stats, total_time)
            give_build_book(rcon, player_name, {
                "prompt": prompt,
                "model": model,
                "block_count": stats["block_count"],
                "cmd_count": stats.get("cmd_count", 0),
                "input_tokens": stats["input_tokens"],
                "output_tokens": stats["output_tokens"],
                "cost": stats["cost"],
                "build_time": total_time,
                "attempts": stats["attempts"],
                "coords": stats.get("coords", (0, 64, 0)),
                "code": stats.get("code", ""),
            })
        else:
            bar.fail("Build failed")

    except Exception as e:
        error_msg = str(e)[:200]
        print(f"[AI Builder] Error: {traceback.format_exc()}")
        bar.cancel()
        try:
            _tell(rcon, player_name, {"text": f"Build failed: {error_msg}", "color": "red"})
        except Exception:
            pass
        try:
            rcon.reconnect()
        except Exception:
            pass


def poll_plugin_queue(rcon):
    if not os.path.isdir(PLUGIN_QUEUE_DIR):
        return []

    commands = []
    try:
        files = sorted(os.listdir(PLUGIN_QUEUE_DIR))
    except OSError:
        return []

    for fname in files:
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(PLUGIN_QUEUE_DIR, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            os.remove(fpath)
            commands.append(data)
        except Exception as e:
            print(f"[AI Builder] Error reading queue file {fname}: {e}")
            try:
                os.remove(fpath)
            except Exception:
                pass

    return commands


def ensure_rcon(rcon):
    if not rcon.sock:
        rcon.connect()
    return rcon


def watch_chat():
    print("[AI Builder] Starting chat watcher...")
    print(f"[AI Builder] Watching plugin queue: {PLUGIN_QUEUE_DIR}")
    print(f"[AI Builder] Also watching log file: {LOG_FILE}")

    rcon = RconClient()
    try:
        rcon.connect()
        print("[AI Builder] Connected to RCON")
        rcon.command("gamerule sendCommandFeedback false")
        rcon.command("gamerule commandBlockOutput false")
        print("[AI Builder] Disabled command feedback in chat")
    except Exception as e:
        print(f"[AI Builder] RCON connection failed: {e}")
        print("[AI Builder] Will retry on first command...")

    while not os.path.exists(LOG_FILE):
        print(f"[AI Builder] Waiting for log file to appear...")
        time.sleep(5)

    chat_pattern = re.compile(r'\[.*?INFO\].*?:\s*<(\w+)>\s*(.*)')

    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)
        print("[AI Builder] Watching for commands (/ via plugin, ! via chat)...")

        while True:
            queued = poll_plugin_queue(rcon)
            for cmd_data in queued:
                player_name = cmd_data.get("player", "")
                command_str = cmd_data.get("command", "")
                prompt = cmd_data.get("prompt", "")

                if not player_name or not command_str:
                    continue

                print(f"[AI Builder] Plugin command: /{command_str} from {player_name}")

                try:
                    ensure_rcon(rcon)
                except Exception as e:
                    print(f"[AI Builder] RCON reconnect failed: {e}")
                    continue

                process_command(rcon, player_name, command_str, prompt)

            line = f.readline()
            if not line:
                time.sleep(0.2)
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

            cmd_text = message[1:]
            parts = cmd_text.split(" ", 1)
            cmd_key = parts[0]
            prompt = parts[1] if len(parts) > 1 else ""

            process_command(rcon, player_name, cmd_key, prompt)


if __name__ == "__main__":
    watch_chat()
