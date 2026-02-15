import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { mineclawPlugin } from "./src/channel.js";
import { MineclawConfigSchema } from "./src/config-schema.js";
import { setMineclawRuntime } from "./src/runtime.js";

const plugin = {
  id: "mineclaw",
  name: "MineClaw",
  description: "Minecraft channel plugin — chat with players and control bots",
  configSchema: MineclawConfigSchema,
  register(api: OpenClawPluginApi) {
    setMineclawRuntime(api.runtime);
    api.registerChannel({ plugin: mineclawPlugin });
  },
};

export default plugin;
