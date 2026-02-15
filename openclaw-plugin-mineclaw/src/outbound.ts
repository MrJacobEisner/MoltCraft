import type { ResolvedMineclawAccount } from "./types.js";

export interface SendResult {
  ok: boolean;
  error?: string;
}

export async function sendMessageToMinecraft(
  account: ResolvedMineclawAccount,
  text: string,
  target?: string,
): Promise<SendResult> {
  const url = `${account.apiUrl.replace(/\/+$/, "")}/api/chat/send`;
  const body: Record<string, string> = { message: text };
  if (target) {
    body.target = target;
  }

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${account.apiKey}`,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      return { ok: false, error: `HTTP ${response.status}: ${errorText}` };
    }

    return { ok: true };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: message };
  }
}

export async function checkMineclawStatus(
  account: ResolvedMineclawAccount,
  timeoutMs = 5000,
): Promise<{ ok: boolean; error?: string; serverOnline?: boolean }> {
  const url = `${account.apiUrl.replace(/\/+$/, "")}/api/status`;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${account.apiKey}` },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      return { ok: false, error: `HTTP ${response.status}` };
    }

    const data = (await response.json()) as Record<string, unknown>;
    return {
      ok: true,
      serverOnline: data.server_online === true,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: message };
  }
}