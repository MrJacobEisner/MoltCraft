import json
import time


MAX_CHARS_PER_PAGE = 250
MAX_CODE_PAGES = 6


def _escape_snbt(text):
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")


def _make_page(components):
    parts = []
    for comp in components:
        if isinstance(comp, dict):
            parts.append(json.dumps(comp, ensure_ascii=False))
        else:
            parts.append(json.dumps({"text": comp}, ensure_ascii=False))
    return "'[" + ",".join(parts) + "]'"


def _split_code_pages(code):
    lines = code.split("\n")
    pages = []
    current_chunk = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > MAX_CHARS_PER_PAGE and current_chunk:
            pages.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += line_len
    if current_chunk:
        pages.append("\n".join(current_chunk))
    return pages[:MAX_CODE_PAGES]


def give_build_book(rcon, player_name, stats):
    prompt = stats.get("prompt", "Unknown")
    model = stats.get("model", "Unknown")
    block_count = stats.get("block_count", 0)
    cmd_count = stats.get("cmd_count", 0)
    input_tokens = stats.get("input_tokens", 0)
    output_tokens = stats.get("output_tokens", 0)
    cost = stats.get("cost", 0.0)
    build_time = stats.get("build_time", 0.0)
    attempts = stats.get("attempts", 1)
    coords = stats.get("coords", (0, 64, 0))
    code = stats.get("code", "")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    cost_str = f"${cost:.4f}" if cost < 0.01 else f"${cost:.3f}"
    coord_str = f"{coords[0]}, {coords[1]}, {coords[2]}"
    prompt_display = prompt[:100] + "..." if len(prompt) > 100 else prompt

    page1 = _make_page([
        {"text": "AI Build Report\\n\\n", "color": "gold", "bold": True},
        {"text": "Prompt: ", "color": "dark_aqua", "bold": True},
        {"text": f"{_escape_snbt(prompt_display)}\\n\\n", "color": "black"},
        {"text": "Model: ", "color": "dark_aqua", "bold": True},
        {"text": f"{_escape_snbt(model)}\\n\\n", "color": "black"},
        {"text": "Date: ", "color": "dark_aqua", "bold": True},
        {"text": f"{timestamp}\\n", "color": "black"},
    ])

    page2 = _make_page([
        {"text": "Build Stats\\n\\n", "color": "gold", "bold": True},
        {"text": "Blocks: ", "color": "dark_aqua", "bold": True},
        {"text": f"{block_count:,}\\n", "color": "black"},
        {"text": "Commands: ", "color": "dark_aqua", "bold": True},
        {"text": f"{cmd_count:,}\\n", "color": "black"},
        {"text": "Coordinates: ", "color": "dark_aqua", "bold": True},
        {"text": f"{coord_str}\\n", "color": "black"},
        {"text": "Build Time: ", "color": "dark_aqua", "bold": True},
        {"text": f"{build_time:.1f}s\\n", "color": "black"},
        {"text": "Attempts: ", "color": "dark_aqua", "bold": True},
        {"text": f"{attempts}\\n", "color": "black"},
    ])

    page3 = _make_page([
        {"text": "Token Usage\\n\\n", "color": "gold", "bold": True},
        {"text": "Input: ", "color": "dark_aqua", "bold": True},
        {"text": f"{input_tokens:,} tokens\\n", "color": "black"},
        {"text": "Output: ", "color": "dark_aqua", "bold": True},
        {"text": f"{output_tokens:,} tokens\\n", "color": "black"},
        {"text": "Total: ", "color": "dark_aqua", "bold": True},
        {"text": f"{input_tokens + output_tokens:,} tokens\\n\\n", "color": "black"},
        {"text": "Cost: ", "color": "dark_aqua", "bold": True},
        {"text": f"{cost_str}\\n", "color": "dark_green"},
    ])

    pages = [page1, page2, page3]

    code_chunks = _split_code_pages(code)
    for i, chunk in enumerate(code_chunks):
        header = "Code" if i == 0 else "Code (cont.)"
        page_num = f" [{i + 1}/{len(code_chunks)}]" if len(code_chunks) > 1 else ""
        code_page = _make_page([
            {"text": f"{header}{page_num}\\n\\n", "color": "gold", "bold": True},
            {"text": _escape_snbt(chunk), "color": "dark_gray"},
        ])
        pages.append(code_page)

    pages_str = ",".join(pages)
    title = _escape_snbt(f"Build: {prompt[:25]}")

    cmd = (
        f'give {player_name} written_book['
        f'written_book_content={{'
        f'pages:[{pages_str}],'
        f'title:"{title}",'
        f'author:"AI Builder"'
        f'}}]'
    )

    time.sleep(1)
    try:
        rcon.reconnect()
    except Exception:
        pass

    try:
        rcon.command(cmd)
    except Exception as e:
        print(f"[AI Builder] Book command too long or failed ({len(cmd)} chars), trying short version: {e}")
        short_page1 = _make_page([
            {"text": "AI Build Report\\n\\n", "color": "gold", "bold": True},
            {"text": "Prompt: ", "color": "dark_aqua", "bold": True},
            {"text": f"{_escape_snbt(prompt_display)}\\n\\n", "color": "black"},
            {"text": "Model: ", "color": "dark_aqua", "bold": True},
            {"text": f"{_escape_snbt(model)}\\n", "color": "black"},
        ])
        short_page2 = _make_page([
            {"text": "Build Stats\\n\\n", "color": "gold", "bold": True},
            {"text": f"Blocks: {block_count:,}\\n", "color": "black"},
            {"text": f"Commands: {cmd_count:,}\\n", "color": "black"},
            {"text": f"Time: {build_time:.1f}s\\n", "color": "black"},
            {"text": f"Cost: {cost_str}\\n", "color": "dark_green"},
            {"text": f"Location: {coord_str}\\n", "color": "black"},
        ])
        short_cmd = (
            f'give {player_name} written_book['
            f'written_book_content={{'
            f'pages:[{short_page1},{short_page2}],'
            f'title:"{title}",'
            f'author:"AI Builder"'
            f'}}]'
        )
        try:
            rcon.command(short_cmd)
        except Exception as e2:
            print(f"[AI Builder] Failed to give short book too: {e2}")
