import * as http from "node:http";
import type { MineclawInboundMessage, WebhookServerOptions } from "./types.js";

export class WebhookServer {
  private server: http.Server | null = null;
  private port: number;
  private token: string;
  private onMessage: (msg: MineclawInboundMessage) => void;

  constructor(options: WebhookServerOptions) {
    this.port = options.port;
    this.token = options.token;
    this.onMessage = options.onMessage;
  }

  async start(): Promise<void> {
    if (this.server) return;

    this.server = http.createServer((req, res) => {
      if (req.method === "POST" && req.url === "/webhook") {
        this.handleWebhook(req, res);
      } else if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", channel: "mineclaw" }));
      } else {
        res.writeHead(404);
        res.end("Not found");
      }
    });

    return new Promise<void>((resolve, reject) => {
      this.server!.on("error", reject);
      this.server!.listen(this.port, "0.0.0.0", () => {
        resolve();
      });
    });
  }

  async stop(): Promise<void> {
    if (!this.server) return;
    return new Promise<void>((resolve) => {
      this.server!.close(() => {
        this.server = null;
        resolve();
      });
    });
  }

  private handleWebhook(req: http.IncomingMessage, res: http.ServerResponse): void {
    const authHeader = req.headers.authorization;
    if (this.token) {
      if (!authHeader || authHeader !== `Bearer ${this.token}`) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Unauthorized" }));
        return;
      }
    }

    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1024 * 64) {
        res.writeHead(413);
        res.end("Payload too large");
        req.destroy();
      }
    });

    req.on("end", () => {
      try {
        const data = JSON.parse(body) as MineclawInboundMessage;
        if (!data.player || !data.message) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Missing player or message" }));
          return;
        }
        this.onMessage(data);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ success: true }));
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid JSON" }));
      }
    });
  }

  get isRunning(): boolean {
    return this.server !== null && this.server.listening;
  }

  get listenPort(): number {
    return this.port;
  }
}