import type { OpenClawConfig } from "openclaw/plugin-sdk";
import { buildChannelConfigSchema } from "openclaw/plugin-sdk";
import { getMineclawRuntime } from "./runtime.js";
import { MineclawConfigSchema } from "./config-schema.js";
import { WebhookServer } from "./webhook-server.js";
import { sendMessageToMinecraft, checkMineclawStatus } from "./outbound.js";
import type {
  MineclawConfig,
  ResolvedMineclawAccount,
  MineclawInboundMessage,
} from "./types.js";

const DEFAULT_WEBHOOK_PORT = 18790;
const DEFAULT_WEBHOOK_TOKEN = "";

const meta = {
  id: "mineclaw",
  label: "MineClaw",
  selectionLabel: "MineClaw (Minecraft)",
  docsPath: "/channels/mineclaw",
  docsLabel: "mineclaw",
  blurb: "Minecraft chat via MineClaw server.",
  order: 80,
  aliases: ["mc", "minecraft"],
};

const webhookServers = new Map<string, WebhookServer>();

function getConfig(cfg: OpenClawConfig, accountId?: string): MineclawConfig {
  const mcCfg = (cfg as any)?.channels?.mineclaw as MineclawConfig | undefined;
  if (!mcCfg) return {} as MineclawConfig;
  if (accountId && mcCfg.accounts?.[accountId]) {
    return { ...mcCfg, ...mcCfg.accounts[accountId] };
  }
  return mcCfg;
}

function resolveAccount(
  cfg: OpenClawConfig,
  accountId?: string,
): ResolvedMineclawAccount {
  const config = getConfig(cfg, accountId);
  return {
    accountId: accountId ?? "default",
    name: (config as any).name,
    enabled: config.enabled !== false,
    configured: Boolean(config.apiUrl && config.apiKey),
    apiUrl: config.apiUrl ?? "",
    apiKey: config.apiKey ?? "",
    webhookPort: config.webhookPort ?? DEFAULT_WEBHOOK_PORT,
    webhookToken: config.webhookToken ?? DEFAULT_WEBHOOK_TOKEN,
  };
}

function handleInboundMessage(
  msg: MineclawInboundMessage,
  accountId: string,
): void {
  const runtime = getMineclawRuntime();

  const positionInfo = msg.position
    ? ` (at ${msg.position.x}, ${msg.position.y}, ${msg.position.z})`
    : "";

  const envelope = {
    channel: "mineclaw",
    accountId,
    from: msg.player,
    fromLabel: msg.player,
    text: msg.message,
    metadata: {
      player: msg.player,
      position: msg.position,
      positionInfo,
    },
  };

  runtime.emitInbound(envelope);
}

export const mineclawPlugin = {
  id: "mineclaw",
  meta,

  capabilities: {
    chatTypes: ["direct"] as const,
  },

  reload: { configPrefixes: ["channels.mineclaw"] },
  configSchema: buildChannelConfigSchema(MineclawConfigSchema),

  config: {
    listAccountIds: (cfg: OpenClawConfig) => {
      const mcCfg = (cfg as any)?.channels?.mineclaw as
        | MineclawConfig
        | undefined;
      if (!mcCfg?.accounts) return ["default"];
      return ["default", ...Object.keys(mcCfg.accounts)];
    },

    resolveAccount: (cfg: OpenClawConfig, accountId?: string) =>
      resolveAccount(cfg, accountId),

    defaultAccountId: () => "default",

    isConfigured: (account: ResolvedMineclawAccount) => account.configured,

    describeAccount: (account: ResolvedMineclawAccount) => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured,
      baseUrl: account.apiUrl,
    }),
  },

  security: {
    resolveDmPolicy: ({
      account,
      cfg,
    }: {
      account: ResolvedMineclawAccount;
      cfg: OpenClawConfig;
    }) => {
      const config = getConfig(cfg, account.accountId);
      const dmConfig = (config as any).dm;
      const policy = dmConfig?.policy ?? "open";
      const allowFrom = dmConfig?.allowFrom ?? (policy === "open" ? ["*"] : []);
      const prefix =
        account.accountId && account.accountId !== "default"
          ? `channels.mineclaw.accounts.${account.accountId}.dm`
          : "channels.mineclaw.dm";
      return {
        policy,
        allowFrom,
        policyPath: `${prefix}.policy`,
        allowFromPath: `${prefix}.allowFrom`,
      };
    },
  },

  messaging: {
    normalizeTarget: (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed) return undefined;
      const lowered = trimmed.toLowerCase();
      if (lowered.startsWith("mineclaw:")) {
        return trimmed.slice("mineclaw:".length).trim() || undefined;
      }
      return trimmed || undefined;
    },
  },

  gateway: {
    start: async ({
      cfg,
      accountId,
      log,
    }: {
      cfg: OpenClawConfig;
      accountId: string;
      log: any;
    }) => {
      const account = resolveAccount(cfg, accountId);

      if (!account.configured) {
        log?.warn?.(
          "[MineClaw] Not configured — set channels.mineclaw.apiUrl and channels.mineclaw.apiKey",
        );
        return { running: false, lastError: "Not configured" };
      }

      if (!account.webhookToken) {
        log?.warn?.(
          "[MineClaw] No webhookToken set — webhook endpoint will accept unauthenticated requests. Set channels.mineclaw.webhookToken for security.",
        );
      }

      const serverKey = `${accountId}:${account.webhookPort}`;

      if (webhookServers.has(serverKey)) {
        await webhookServers.get(serverKey)!.stop();
        webhookServers.delete(serverKey);
      }

      const webhookServer = new WebhookServer({
        port: account.webhookPort,
        token: account.webhookToken,
        onMessage: (msg) => handleInboundMessage(msg, accountId),
      });

      try {
        await webhookServer.start();
        webhookServers.set(serverKey, webhookServer);
        log?.info?.(
          `[MineClaw] Webhook server listening on port ${account.webhookPort}`,
        );
      } catch (err) {
        const error =
          err instanceof Error ? err.message : String(err);
        log?.error?.(`[MineClaw] Failed to start webhook server: ${error}`);
        return { running: false, lastError: error };
      }

      const status = await checkMineclawStatus(account);
      if (status.ok) {
        log?.info?.(
          `[MineClaw] Connected to MineClaw server at ${account.apiUrl} (server ${status.serverOnline ? "online" : "starting"})`,
        );
      } else {
        log?.warn?.(
          `[MineClaw] Could not reach MineClaw server at ${account.apiUrl}: ${status.error}`,
        );
      }

      return {
        running: true,
        lastStartAt: Date.now(),
        lastError: null,
      };
    },

    stop: async ({ accountId, log }: { accountId: string; log: any }) => {
      for (const [key, server] of webhookServers.entries()) {
        if (key.startsWith(`${accountId}:`)) {
          await server.stop();
          webhookServers.delete(key);
          log?.info?.("[MineClaw] Webhook server stopped");
        }
      }
      return { running: false, lastStopAt: Date.now() };
    },
  },

  outbound: {
    deliveryMode: "direct" as const,

    sendText: async ({
      text,
      target,
      cfg,
      accountId,
    }: {
      text: string;
      target?: string;
      cfg: OpenClawConfig;
      accountId?: string;
    }) => {
      const account = resolveAccount(cfg, accountId);
      if (!account.configured) {
        return { ok: false, error: "MineClaw not configured" };
      }

      const playerTarget = target
        ? target.replace(/^(user:|mineclaw:)/i, "")
        : undefined;

      const result = await sendMessageToMinecraft(
        account,
        text,
        playerTarget,
      );
      return result;
    },
  },

  status: {
    defaultRuntime: {
      accountId: "default",
      running: false,
      lastStartAt: null,
      lastStopAt: null,
      lastError: null,
    },

    collectStatusIssues: (
      accounts: Array<{ accountId: string; lastError?: string | null }>,
    ) =>
      accounts.flatMap((account) => {
        const lastError =
          typeof account.lastError === "string"
            ? account.lastError.trim()
            : "";
        if (!lastError) return [];
        return [
          {
            channel: "mineclaw",
            accountId: account.accountId,
            kind: "runtime",
            message: `Channel error: ${lastError}`,
          },
        ];
      }),

    buildChannelSummary: ({ snapshot }: { snapshot: any }) => ({
      configured: snapshot.configured ?? false,
      baseUrl: snapshot.baseUrl ?? null,
      running: snapshot.running ?? false,
      lastStartAt: snapshot.lastStartAt ?? null,
      lastStopAt: snapshot.lastStopAt ?? null,
      lastError: snapshot.lastError ?? null,
    }),

    probeAccount: async ({
      account,
      timeoutMs,
    }: {
      account: ResolvedMineclawAccount;
      timeoutMs?: number;
    }) => {
      const result = await checkMineclawStatus(account, timeoutMs);
      return {
        ok: result.ok,
        error: result.error,
        elapsedMs: 0,
        serverOnline: result.serverOnline,
      };
    },

    buildAccountSnapshot: ({
      account,
      runtime: rt,
    }: {
      account: ResolvedMineclawAccount;
      runtime?: any;
    }) => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured,
      baseUrl: account.apiUrl,
      webhookPort: account.webhookPort,
      running: rt?.running ?? false,
      lastStartAt: rt?.lastStartAt ?? null,
      lastStopAt: rt?.lastStopAt ?? null,
      lastError: rt?.lastError ?? null,
    }),
  },

  setup: {
    validateInput: ({
      input,
    }: {
      input: { apiUrl?: string; apiKey?: string; useEnv?: boolean };
    }) => {
      if (input.useEnv) return null;
      if (!input.apiUrl?.trim()) return "MineClaw requires --api-url";
      if (!input.apiKey?.trim()) return "MineClaw requires --api-key";
      return null;
    },

    applyAccountConfig: ({
      cfg,
      input,
    }: {
      cfg: OpenClawConfig;
      input: {
        apiUrl?: string;
        apiKey?: string;
        webhookPort?: number;
        webhookToken?: string;
        useEnv?: boolean;
      };
    }) => {
      const existing = (cfg as any).channels?.mineclaw ?? {};
      return {
        ...cfg,
        channels: {
          ...(cfg as any).channels,
          mineclaw: {
            ...existing,
            enabled: true,
            ...(input.apiUrl ? { apiUrl: input.apiUrl.trim() } : {}),
            ...(input.apiKey ? { apiKey: input.apiKey.trim() } : {}),
            ...(input.webhookPort ? { webhookPort: input.webhookPort } : {}),
            ...(input.webhookToken
              ? { webhookToken: input.webhookToken.trim() }
              : {}),
          },
        },
      };
    },
  },

  directory: {
    self: async () => null,
    listPeers: async () => [],
    listGroups: async () => [],
  },
};
