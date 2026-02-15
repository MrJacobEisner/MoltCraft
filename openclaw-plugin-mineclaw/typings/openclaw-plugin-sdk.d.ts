declare module "openclaw/plugin-sdk" {
  export interface OpenClawConfig {
    channels?: Record<string, unknown>;
    [key: string]: unknown;
  }

  export interface PluginRuntime {
    emitInbound(event: {
      channel: string;
      accountId: string;
      from: string;
      fromLabel?: string;
      text: string;
      metadata?: unknown;
      [key: string]: unknown;
    }): void;
    [key: string]: unknown;
  }

  export interface OpenClawPluginApi {
    runtime: PluginRuntime;
    registerChannel(opts: { plugin: unknown }): void;
    [key: string]: unknown;
  }

  export function buildChannelConfigSchema(schema: unknown): unknown;
  export function emptyPluginConfigSchema(): unknown;
}
