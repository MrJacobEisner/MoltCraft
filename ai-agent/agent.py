import os
import json
import time
import requests
import traceback

BOT_API = "http://localhost:3001"
MAX_ITERATIONS = 50
TOOL_TIMEOUT = 60

def get_bot_status():
    try:
        r = requests.get(f"{BOT_API}/status", timeout=5)
        return r.json()
    except Exception:
        return None

def get_tool_definitions():
    try:
        r = requests.get(f"{BOT_API}/tools", timeout=5)
        return r.json()
    except Exception:
        return []

def execute_tool(tool_name, tool_input):
    try:
        r = requests.post(f"{BOT_API}/execute", json={"tool": tool_name, "input": tool_input}, timeout=TOOL_TIMEOUT)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def set_task(task, player_name):
    try:
        r = requests.post(f"{BOT_API}/task", json={"task": task, "player_name": player_name}, timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def clear_task():
    try:
        requests.post(f"{BOT_API}/task/clear", timeout=5)
    except Exception:
        pass

def send_chat(message):
    execute_tool("chat", {"message": message})

def _get_system_prompt(player_name):
    return f"""You are ClaudeBot, an autonomous AI agent inside a Minecraft server. You are a real player in the game world — you can walk, mine, craft, place blocks, collect items, and interact with the environment.

A player named "{player_name}" has given you a task to complete. You must figure out how to accomplish it step by step, using the tools available to you.

IMPORTANT RULES:
1. Always start by observing your surroundings with look_around to understand where you are.
2. Think step by step. Plan what you need to do before acting.
3. Use navigate_to or navigate_to_player to move around. You walk with real A* pathfinding.
4. When mining blocks, first scan for them with scan_nearby_blocks, then use mine_type to mine them.
5. You can craft items if you have the right materials. Use craft_item.
6. When you're done, use task_complete to report what you did.
7. If you get stuck or the task is impossible, use task_failed to explain why.
8. Send chat messages to keep the player informed of your progress.
9. Be efficient — don't wander aimlessly. Think, then act.
10. You exist in a flat creative world, but you interact with it like survival — mining drops items, crafting requires materials.
11. If you need to give items to the player, navigate to them first, then use toss_to_player.
12. Collect dropped items after mining by using collect_nearby_items or just walking over them.

You have access to a full Minecraft inventory and can pick up dropped items by walking near them. You are a real player entity in the game.

Remember: This is a FLAT WORLD (superflat). The ground is grass/dirt at around y=-60. Trees may need to be found or may not exist in a flat world — adapt your approach if needed."""


def _convert_tools_to_gemini(raw_tools):
    from google.genai import types

    declarations = []
    for t in raw_tools:
        schema = t.get("input_schema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])

        gemini_props = {}
        for prop_name, prop_def in props.items():
            prop_type = prop_def.get("type", "string").upper()
            type_map = {
                "STRING": types.Type.STRING,
                "NUMBER": types.Type.NUMBER,
                "INTEGER": types.Type.INTEGER,
                "BOOLEAN": types.Type.BOOLEAN,
                "ARRAY": types.Type.ARRAY,
                "OBJECT": types.Type.OBJECT,
            }
            gemini_type = type_map.get(prop_type, types.Type.STRING)

            schema_kwargs = {
                "type": gemini_type,
                "description": prop_def.get("description", ""),
            }

            if gemini_type == types.Type.ARRAY and "items" in prop_def:
                items_type = prop_def["items"].get("type", "string").upper()
                schema_kwargs["items"] = types.Schema(
                    type=type_map.get(items_type, types.Type.STRING)
                )

            gemini_props[prop_name] = types.Schema(**schema_kwargs)

        params = types.Schema(
            type=types.Type.OBJECT,
            properties=gemini_props,
            required=required if required else None,
        )

        declarations.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=params,
            )
        )

    return types.Tool(function_declarations=declarations)


def run_agent_loop(task, player_name, status_callback=None):
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY"),
        http_options={
            "api_version": "",
            "base_url": os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL"),
        },
    )

    status = get_bot_status()
    if not status or not status.get("connected"):
        return {"success": False, "error": "Bot is not connected to the server"}

    result = set_task(task, player_name)
    if "error" in result:
        return {"success": False, "error": result["error"]}

    raw_tools = get_tool_definitions()
    gemini_tools = _convert_tools_to_gemini(raw_tools)

    system_prompt = _get_system_prompt(player_name)
    config = types.GenerateContentConfig(
        tools=[gemini_tools],
        system_instruction=system_prompt,
        max_output_tokens=8192,
    )

    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=f"Task from {player_name}: {task}")],
        )
    ]

    if status_callback:
        status_callback(f"Starting task: {task}")

    send_chat(f"Got it! Working on: {task}")

    for iteration in range(MAX_ITERATIONS):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=contents,
                config=config,
            )
        except Exception as e:
            error_msg = f"AI error: {str(e)[:200]}"
            print(f"[Agent] {error_msg}")
            send_chat(f"Error: {str(e)[:100]}")
            clear_task()
            return {"success": False, "error": error_msg}

        if not response.candidates or not response.candidates[0].content:
            print("[Agent] Empty response from AI")
            send_chat("Got an empty response, stopping.")
            clear_task()
            return {"success": False, "error": "Empty AI response"}

        content = response.candidates[0].content

        function_calls = []
        text_parts = []
        for part in content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_calls.append(part.function_call)
            elif hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        if not function_calls:
            final_text = " ".join(text_parts) if text_parts else "Task processing complete"
            print(f"[Agent] AI ended turn: {final_text[:200]}")
            send_chat(final_text[:200])
            clear_task()
            return {"success": True, "message": final_text}

        contents.append(content)

        function_response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            tool_input = dict(fc.args) if fc.args else {}
            print(f"[Agent] [{iteration+1}/{MAX_ITERATIONS}] Calling: {tool_name}({json.dumps(tool_input)[:100]})")

            if status_callback:
                status_callback(f"Step {iteration+1}: {tool_name}")

            result = execute_tool(tool_name, tool_input)
            print(f"[Agent] Result: {json.dumps(result)[:200]}")

            if result.get("task_done"):
                clear_task()
                summary = result.get("summary") or result.get("reason", "Done")
                status_str = result.get("status", "complete")
                send_chat(f"Task {status_str}: {summary}")
                return {
                    "success": status_str == "complete",
                    "message": summary,
                }

            function_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response=result,
                    )
                )
            )

        contents.append(
            types.Content(role="user", parts=function_response_parts)
        )

        if len(contents) > 80:
            contents = contents[:2] + contents[-40:]

    send_chat("Reached maximum steps, stopping.")
    clear_task()
    return {"success": False, "error": "Reached maximum iteration limit"}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python agent.py <player_name> <task>")
        sys.exit(1)

    player = sys.argv[1]
    task = " ".join(sys.argv[2:])
    print(f"[Agent] Running task for {player}: {task}")
    result = run_agent_loop(task, player)
    print(f"[Agent] Result: {json.dumps(result)}")
