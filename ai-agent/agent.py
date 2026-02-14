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


def run_agent_loop(task, player_name, status_callback=None):
    from anthropic import Anthropic

    client = Anthropic(
        api_key=os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY"),
        base_url=os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
    )

    status = get_bot_status()
    if not status or not status.get("connected"):
        return {"success": False, "error": "Bot is not connected to the server"}

    result = set_task(task, player_name)
    if "error" in result:
        return {"success": False, "error": result["error"]}

    raw_tools = get_tool_definitions()
    tools = []
    for t in raw_tools:
        tools.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"]
        })

    system = _get_system_prompt(player_name)
    messages = [
        {"role": "user", "content": f"Task from {player_name}: {task}"}
    ]

    if status_callback:
        status_callback(f"Starting task: {task}")

    send_chat(f"Got it! Working on: {task}")

    for iteration in range(MAX_ITERATIONS):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250514",
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=messages
            )
        except Exception as e:
            error_msg = f"AI error: {str(e)[:200]}"
            print(f"[Agent] {error_msg}")
            send_chat(f"Error: {str(e)[:100]}")
            clear_task()
            return {"success": False, "error": error_msg}

        if response.stop_reason == "end_turn":
            text_parts = [b.text for b in response.content if hasattr(b, 'text')]
            final_text = " ".join(text_parts) if text_parts else "Task processing complete"
            print(f"[Agent] AI ended turn: {final_text[:200]}")
            send_chat(final_text[:200])
            clear_task()
            return {"success": True, "message": final_text}

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            text_parts = [b.text for b in response.content if hasattr(b, 'text')]
            final_text = " ".join(text_parts) if text_parts else "Done"
            clear_task()
            return {"success": True, "message": final_text}

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input
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
                    "message": summary
                }

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result)
            })

        messages.append({"role": "user", "content": tool_results})

        if len(messages) > 80:
            keep = messages[:2] + messages[-40:]
            messages = keep

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
