package com.aibuilder;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

public class AICommandExecutor implements CommandExecutor {

    private final AIBuilderPlugin plugin;
    private final File queueDir;

    public AICommandExecutor(AIBuilderPlugin plugin, File queueDir) {
        this.plugin = plugin;
        this.queueDir = queueDir;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player)) {
            sender.sendMessage("This command can only be used by players.");
            return true;
        }

        Player player = (Player) sender;
        String cmdName = command.getName().toLowerCase();

        if (cmdName.equals("aihelp") || cmdName.equals("models")) {
            writeToQueue(player.getName(), cmdName, "");
            return true;
        }

        if (args.length == 0) {
            player.sendMessage("\u00a7cUsage: /" + cmdName + " <prompt>");
            player.sendMessage("\u00a77Example: /" + cmdName + " build a medieval castle");
            return true;
        }

        String prompt = String.join(" ", args);

        String subModel = "";
        if (prompt.startsWith(":") && prompt.contains(" ")) {
            int spaceIdx = prompt.indexOf(" ");
            subModel = prompt.substring(1, spaceIdx);
            prompt = prompt.substring(spaceIdx + 1).trim();
        }

        String fullCommand = cmdName;
        if (!subModel.isEmpty()) {
            fullCommand = cmdName + ":" + subModel;
        }

        player.sendMessage("\u00a7b[AI Builder] \u00a77Processing your request with \u00a7e" + fullCommand + "\u00a77...");
        writeToQueue(player.getName(), fullCommand, prompt);
        return true;
    }

    private void writeToQueue(String playerName, String command, String prompt) {
        try {
            long timestamp = System.currentTimeMillis();
            String json = String.format(
                "{\"player\":\"%s\",\"command\":\"%s\",\"prompt\":\"%s\",\"timestamp\":%d}",
                escapeJson(playerName),
                escapeJson(command),
                escapeJson(prompt),
                timestamp
            );

            File queueFile = new File(queueDir, "cmd_" + timestamp + ".json");
            try (FileWriter writer = new FileWriter(queueFile)) {
                writer.write(json);
            }

            plugin.getLogger().info("Queued command: /" + command + " from " + playerName);
        } catch (IOException e) {
            plugin.getLogger().severe("Failed to write command to queue: " + e.getMessage());
        }
    }

    private String escapeJson(String input) {
        if (input == null) return "";
        return input.replace("\\", "\\\\")
                     .replace("\"", "\\\"")
                     .replace("\n", "\\n")
                     .replace("\r", "\\r")
                     .replace("\t", "\\t");
    }
}
