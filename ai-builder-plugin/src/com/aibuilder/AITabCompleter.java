package com.aibuilder;

import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;

import java.util.*;

public class AITabCompleter implements TabCompleter {

    private static final Map<String, List<String>> SUB_MODELS = new HashMap<>();

    static {
        SUB_MODELS.put("claude", Arrays.asList(":sonnet", ":haiku"));
        SUB_MODELS.put("openai", Arrays.asList(":o4-mini", ":gpt-5.1", ":gpt-5-mini"));
        SUB_MODELS.put("gemini", Arrays.asList(":flash", ":pro"));
        SUB_MODELS.put("deepseek", Arrays.asList(":v3", ":r1"));
        SUB_MODELS.put("kimi", Arrays.asList(":k2.5"));
        SUB_MODELS.put("grok", Arrays.asList(":grok-4"));
        SUB_MODELS.put("glm", Arrays.asList(":glm-5"));
    }

    private static final List<String> EXAMPLE_PROMPTS = Arrays.asList(
        "build a castle",
        "build a medieval house",
        "build a modern skyscraper",
        "build a japanese temple",
        "build a pirate ship",
        "build a lighthouse",
        "build a fountain",
        "build a tower"
    );

    private static final List<String> AGENT_EXAMPLES = Arrays.asList(
        "come to me",
        "mine 10 oak logs",
        "craft a crafting table",
        "bring me 32 oak planks",
        "explore the area around me",
        "collect all nearby items",
        "place a ring of torches around me"
    );

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        String cmdName = command.getName().toLowerCase();

        if (cmdName.equals("aihelp") || cmdName.equals("models")) {
            return Collections.emptyList();
        }

        if (args.length == 1) {
            String input = args[0].toLowerCase();
            List<String> suggestions = new ArrayList<>();

            if (cmdName.equals("agent")) {
                for (String example : AGENT_EXAMPLES) {
                    if (example.startsWith(input) || input.isEmpty()) {
                        suggestions.add(example);
                    }
                }
                return suggestions;
            }

            if (SUB_MODELS.containsKey(cmdName)) {
                for (String sub : SUB_MODELS.get(cmdName)) {
                    if (sub.startsWith(input) || input.isEmpty()) {
                        suggestions.add(sub);
                    }
                }
            }

            for (String prompt : EXAMPLE_PROMPTS) {
                if (prompt.startsWith(input) || input.isEmpty()) {
                    suggestions.add(prompt);
                }
            }

            return suggestions;
        }

        return Collections.emptyList();
    }
}
