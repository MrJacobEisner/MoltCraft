export interface MineclawConfig {
  enabled?: boolean;
  apiUrl: string;
  apiKey: string;
  webhookPort?: number;
  webhookToken?: string;
  accounts?: Record<string, MineclawAccountConfig>;
}

export interface MineclawAccountConfig {
  enabled?: boolean;
  name?: string;
  apiUrl: string;
  apiKey: string;
  webhookPort?: number;
  webhookToken?: string;
}

export interface ResolvedMineclawAccount {
  accountId: string;
  name?: string;
  enabled: boolean;
  configured: boolean;
  apiUrl: string;
  apiKey: string;
  webhookPort: number;
  webhookToken: string;
}

export interface MineclawInboundMessage {
  player: string;
  message: string;
  position?: {
    x: number;
    y: number;
    z: number;
  };
}

export interface MineclawServerStatus {
  server_online: boolean;
  address?: string;
  bots_active?: number;
  world_mode?: string;
}

export interface WebhookServerOptions {
  port: number;
  token: string;
  onMessage: (msg: MineclawInboundMessage) => void;
}