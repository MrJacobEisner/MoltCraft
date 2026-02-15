import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk";
import { mineclawPlugin } from "./src/channel.js";
import { setMineclawRuntime } from "./src/runtime.js";

const plugin = {
  id: "mineclaw",
  name: "MineClaw",
  description: "Minecraft channel plugin — chat with players and control bots",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    setMineclawRuntime(api.runtime);
    api.registerChannel({ plugin: mineclawPlugin });
  },
};

export default plugin;
