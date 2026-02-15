import type { PluginRuntime } from "openclaw/plugin-sdk";

let runtime: PluginRuntime | null = null;

export function setMineclawRuntime(next: PluginRuntime): void {
  runtime = next;
}

export function getMineclawRuntime(): PluginRuntime {
  if (!runtime) {
    throw new Error("MineClaw runtime not initialized");
  }
  return runtime;
}
