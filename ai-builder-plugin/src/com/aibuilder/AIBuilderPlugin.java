package com.aibuilder;

import org.bukkit.plugin.java.JavaPlugin;

public class AIBuilderPlugin extends JavaPlugin {

    @Override
    public void onEnable() {
        java.io.File queueDir = new java.io.File(getDataFolder(), "queue");
        if (!queueDir.exists()) {
            queueDir.mkdirs();
        }

        AICommandExecutor executor = new AICommandExecutor(this, queueDir);
        AITabCompleter tabCompleter = new AITabCompleter();

        String[] commands = {"claude", "openai", "gemini", "deepseek", "kimi", "grok", "aihelp", "models"};
        for (String cmd : commands) {
            if (getCommand(cmd) != null) {
                getCommand(cmd).setExecutor(executor);
                getCommand(cmd).setTabCompleter(tabCompleter);
            }
        }

        getLogger().info("AI Builder Plugin enabled! Commands: /claude, /openai, /gemini, /deepseek, /kimi, /grok, /aihelp, /models");
    }

    @Override
    public void onDisable() {
        getLogger().info("AI Builder Plugin disabled.");
    }
}
