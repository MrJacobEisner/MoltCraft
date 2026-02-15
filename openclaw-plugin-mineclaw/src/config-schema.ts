import { z } from "zod";

export const MineclawAccountSchema = z.object({
  enabled: z.boolean().optional(),
  name: z.string().optional(),
  apiUrl: z.string().describe("MineClaw server API URL (e.g. https://your-server.replit.app)"),
  apiKey: z.string().describe("MineClaw API bearer token"),
  webhookPort: z.number().int().min(1024).max(65535).optional().default(18790).describe("Port for the webhook listener"),
  webhookToken: z.string().optional().describe("Shared secret for webhook authentication"),
});

export const MineclawConfigSchema = z.object({
  enabled: z.boolean().optional(),
  apiUrl: z.string().optional().describe("MineClaw server API URL"),
  apiKey: z.string().optional().describe("MineClaw API bearer token"),
  webhookPort: z.number().int().min(1024).max(65535).optional().default(18790),
  webhookToken: z.string().optional(),
  accounts: z.record(z.string(), MineclawAccountSchema).optional(),
  dm: z.object({
    policy: z.enum(["open", "pairing", "allowlist", "disabled"]).optional(),
    allowFrom: z.array(z.string()).optional(),
  }).optional(),
});

export type MineclawConfigType = z.infer<typeof MineclawConfigSchema>;