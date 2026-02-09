import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


def is_rate_limit_error(exception):
    error_msg = str(exception)
    return (
        "429" in error_msg
        or "RATELIMIT_EXCEEDED" in error_msg
        or "quota" in error_msg.lower()
        or "rate limit" in error_msg.lower()
        or (hasattr(exception, "status_code") and exception.status_code == 429)
    )


CLAUDE_MODELS = {
    "opus": "claude-opus-4-5",
    "sonnet": "claude-sonnet-4-5",
    "haiku": "claude-haiku-4-5",
}
CLAUDE_DEFAULT = "claude-opus-4-5"

OPENAI_MODELS = {
    "gpt5": "gpt-5.2",
    "gpt-5": "gpt-5.2",
    "gpt-5.2": "gpt-5.2",
    "gpt-5.1": "gpt-5.1",
    "gpt5-mini": "gpt-5-mini",
    "gpt-5-mini": "gpt-5-mini",
    "o4-mini": "o4-mini",
    "o3": "o3",
    "o3-mini": "o3-mini",
}
OPENAI_DEFAULT = "gpt-5.2"

GEMINI_MODELS = {
    "pro": "gemini-3-pro-preview",
    "flash": "gemini-3-flash-preview",
    "2.5-pro": "gemini-2.5-pro",
    "2.5-flash": "gemini-2.5-flash",
}
GEMINI_DEFAULT = "gemini-3-pro-preview"

OPENROUTER_MODELS = {
    "deepseek": "deepseek/deepseek-r1-0528",
    "deepseek-r1": "deepseek/deepseek-r1-0528",
    "deepseek-v3": "deepseek/deepseek-chat-v3-0324",
    "llama": "meta-llama/llama-3-8b-instruct",
    "qwen": "qwen/qwen3-32b-04-28",
    "mistral": "mistralai/mistral-nemo",
    "gemma": "google/gemma-3-27b-it",
    "mercury": "inception/mercury",
}
OPENROUTER_DEFAULT = "deepseek/deepseek-r1-0528"


def get_building_system_prompt():
    return """You are a Minecraft building AI. You write Python scripts that use a MinecraftBuilder helper library to construct structures in Minecraft.

The MinecraftBuilder class is already imported and instantiated as `builder`. The player's position is available as `px`, `py`, `pz` (integers).

Available builder methods:
- builder.place_block(x, y, z, block) - Place a single block
- builder.fill(x1, y1, z1, x2, y2, z2, block) - Fill a region with blocks
- builder.fill_hollow(x1, y1, z1, x2, y2, z2, block) - Fill outline only
- builder.box(x, y, z, width, height, depth, block, hollow=True) - Build a box
- builder.cylinder(cx, cy, cz, radius, height, block, hollow=True) - Build a cylinder
- builder.sphere(cx, cy, cz, radius, block, hollow=True) - Build a sphere
- builder.dome(cx, cy, cz, radius, block, hollow=True) - Build a dome
- builder.pyramid(cx, cy, cz, base_size, block, hollow=True) - Build a pyramid
- builder.line(x1, y1, z1, x2, y2, z2, block) - Draw a line of blocks
- builder.circle(cx, cy, cz, radius, block, axis="y") - Draw a circle
- builder.spiral(cx, cy, cz, radius, height, block, turns=1) - Build a spiral
- builder.arc(cx, cy, cz, radius, start_angle, end_angle, block) - Draw an arc
- builder.stairs(x, y, z, length, direction, block) - Build stairs (direction: north/south/east/west)
- builder.wall(x1, y1, z1, x2, y2, z2, block) - Build a wall (alias for fill)
- builder.floor(x1, y1, z1, x2, z2, block) - Build a floor at y1
- builder.clear_area(x1, y1, z1, x2, y2, z2) - Clear an area to air

Common Minecraft block names: stone, cobblestone, oak_planks, spruce_planks, birch_planks, oak_log, spruce_log, glass, glass_pane, oak_door, iron_door, oak_stairs, stone_stairs, cobblestone_stairs, oak_fence, stone_bricks, mossy_stone_bricks, bricks, sandstone, red_sandstone, quartz_block, smooth_quartz, prismarine, dark_prismarine, deepslate_bricks, polished_deepslate, copper_block, oxidized_copper, tuff_bricks, cherry_planks, bamboo_planks, mud_bricks, packed_mud, glowstone, sea_lantern, torch, lantern, soul_lantern, water, lava, grass_block, dirt, sand, gravel, iron_block, gold_block, diamond_block, emerald_block, netherite_block, obsidian, crying_obsidian, blackstone, polished_blackstone, nether_bricks, red_nether_bricks, end_stone_bricks, purpur_block, purpur_pillar, wool (white_wool, red_wool, etc.), concrete (white_concrete, etc.), terracotta, glazed_terracotta, ice, packed_ice, blue_ice, snow_block, hay_block, bookshelf, chain, iron_bars, ladder, vine, flower_pot, campfire, bell, anvil, brewing_stand, cauldron, chest, barrel, crafting_table, furnace, enchanting_table, lectern, redstone_lamp, target, tnt

RULES:
1. ONLY output a Python code block. No explanations, no markdown outside the code block.
2. Build relative to the player's position (px, py, pz). Place the structure a few blocks in front of them.
3. Use math and loops for complex shapes. The builder library handles individual block placement efficiently.
4. Keep builds reasonable in size (under 5000 blocks total to avoid lag).
5. Be creative with block choices to make builds look good.
6. Use `import math` if you need math functions.
7. The code will be executed directly. Only use `builder` methods, basic Python, and `math`.
8. Start building at px+3, py, pz+3 (offset from player so they can see it being built).

Example - Build a small house:
```python
import math
bx, by, bz = px + 3, py, pz + 3
builder.floor(bx, by, bz, bx + 6, bz + 6, "oak_planks")
builder.box(bx, by + 1, bz, 7, 4, 7, "oak_planks", hollow=True)
builder.fill(bx + 1, by + 4, bz, bx + 5, by + 4, bz + 6, "oak_planks")
for i in range(7):
    builder.place_block(bx + 3, by + 5, bz + i, "oak_planks")
builder.fill(bx + 2, by + 1, bz + 2, bx + 4, by + 3, bz + 4, "air")
builder.place_block(bx + 3, by + 1, bz, "oak_door[half=lower]")
builder.place_block(bx + 3, by + 2, bz, "oak_door[half=upper]")
builder.place_block(bx + 1, by + 2, bz + 3, "glass_pane")
builder.place_block(bx + 5, by + 2, bz + 3, "glass_pane")
builder.place_block(bx + 3, by + 3, bz + 3, "lantern")
```"""


def parse_command(message):
    parts = message.strip().split(" ", 1)
    if len(parts) < 2:
        return None, None, None

    cmd = parts[0].lstrip("!")
    prompt = parts[1]

    if ":" in cmd:
        provider, model_alias = cmd.split(":", 1)
    else:
        provider = cmd
        model_alias = None

    return provider.lower(), model_alias, prompt


def resolve_model(provider, model_alias):
    if provider == "claude":
        if model_alias and model_alias.lower() in CLAUDE_MODELS:
            return CLAUDE_MODELS[model_alias.lower()]
        elif model_alias:
            return model_alias
        return CLAUDE_DEFAULT
    elif provider == "openai":
        if model_alias and model_alias.lower() in OPENAI_MODELS:
            return OPENAI_MODELS[model_alias.lower()]
        elif model_alias:
            return model_alias
        return OPENAI_DEFAULT
    elif provider == "gemini":
        if model_alias and model_alias.lower() in GEMINI_MODELS:
            return GEMINI_MODELS[model_alias.lower()]
        elif model_alias:
            return model_alias
        return GEMINI_DEFAULT
    elif provider == "openrouter":
        if model_alias and model_alias.lower() in OPENROUTER_MODELS:
            return OPENROUTER_MODELS[model_alias.lower()]
        elif model_alias:
            return model_alias
        return OPENROUTER_DEFAULT
    return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_claude(model, prompt):
    from anthropic import Anthropic
    client = Anthropic(
        api_key=os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY"),
        base_url=os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
    )
    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=get_building_system_prompt(),
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_openai(model, prompt):
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
        base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    )
    response = client.chat.completions.create(
        model=model,
        max_completion_tokens=8192,
        messages=[
            {"role": "system", "content": get_building_system_prompt()},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_gemini(model, prompt):
    from google import genai
    client = genai.Client(
        api_key=os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY"),
        http_options={
            "api_version": "",
            "base_url": os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL")
        }
    )
    full_prompt = get_building_system_prompt() + "\n\nUser request: " + prompt
    response = client.models.generate_content(
        model=model,
        contents=full_prompt
    )
    return response.text


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_openrouter(model, prompt):
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ.get("AI_INTEGRATIONS_OPENROUTER_API_KEY"),
        base_url=os.environ.get("AI_INTEGRATIONS_OPENROUTER_BASE_URL")
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": get_building_system_prompt()},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


def generate_build_script(provider, model, prompt):
    if provider == "claude":
        return call_claude(model, prompt)
    elif provider == "openai":
        return call_openai(model, prompt)
    elif provider == "gemini":
        return call_gemini(model, prompt)
    elif provider == "openrouter":
        return call_openrouter(model, prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_available_models_text():
    lines = [
        "Available AI models:",
        "",
        "Claude (Anthropic):",
        "  !claude <prompt>          - Claude Opus 4.5 (default, most powerful)",
        "  !claude:sonnet <prompt>   - Claude Sonnet 4.5 (balanced)",
        "  !claude:haiku <prompt>    - Claude Haiku 4.5 (fastest)",
        "",
        "OpenAI:",
        "  !openai <prompt>          - GPT-5.2 (default, most powerful)",
        "  !openai:gpt-5.1 <prompt>  - GPT-5.1",
        "  !openai:gpt5-mini <prompt>- GPT-5 Mini (cost effective)",
        "  !openai:o4-mini <prompt>  - o4-mini (reasoning model)",
        "",
        "Gemini (Google):",
        "  !gemini <prompt>          - Gemini 3 Pro (default, most powerful)",
        "  !gemini:flash <prompt>    - Gemini 3 Flash (faster)",
        "  !gemini:2.5-pro <prompt>  - Gemini 2.5 Pro",
        "",
        "OpenRouter (Llama, DeepSeek, Mistral, etc.):",
        "  !openrouter:deepseek <prompt>  - DeepSeek R1",
        "  !openrouter:llama <prompt>     - Llama 3",
        "  !openrouter:qwen <prompt>      - Qwen 3",
        "  !openrouter:mistral <prompt>   - Mistral Nemo",
        "  !openrouter:gemma <prompt>     - Gemma 3",
        "",
        "Type !help to see this list in-game.",
    ]
    return "\n".join(lines)
