/**
 * WebChat Bridge — HTTP / WebSocket bridge for web embedding.
 */

import { Request, Response } from "express";
import { SessionManager } from "../session";
import { MessageNormalizer, NormalizedMessage } from "../normalizer";

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";

export interface WebChatConfig {
  /** Allowed origins for CORS (defaults to "*"). */
  allowedOrigins?: string[];
}

export class WebChatBridge {
  private sessions: SessionManager;
  private normalizer: MessageNormalizer;
  private config: WebChatConfig;

  constructor(
    sessions: SessionManager,
    normalizer: MessageNormalizer,
    config: WebChatConfig = {},
  ) {
    this.sessions = sessions;
    this.normalizer = normalizer;
    this.config = config;
  }

  /**
   * Handle an HTTP POST from the web chat widget.
   * Expects JSON: { userId, text, attachments?, metadata? }
   */
  async handleWebhook(req: Request, res: Response): Promise<void> {
    const body = req.body;

    if (!body.text && !body.message) {
      res.status(400).json({ error: "Missing text or message field." });
      return;
    }

    const userId = body.userId || body.user_id || "anonymous";
    const session = await this.sessions.getOrCreateSession("webchat", userId);
    const normalized = this.normalizer.normalize("webchat", body, session.id);

    try {
      const reply = await this.forwardToEngine(normalized, session.threadId);
      res.json({
        response: reply,
        sessionId: session.id,
        threadId: session.threadId,
      });
    } catch (err) {
      console.error("[WebChat] Error processing message:", err);
      res.status(500).json({ error: "Internal error." });
    }
  }

  /** Forward normalized message to ContextForge engine. */
  private async forwardToEngine(
    msg: NormalizedMessage,
    threadId: string,
  ): Promise<string> {
    const res = await fetch(`${ENGINE_URL}/api/v1/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg.text, thread_id: threadId }),
    });
    const data = await res.json();
    return data.response || "Sorry, I could not process that.";
  }

  /**
   * Send a response — for HTTP this is handled inline in handleWebhook.
   * This method is provided for WebSocket / push scenarios.
   */
  async sendResponse(userId: string, text: string): Promise<void> {
    // In a WebSocket implementation this would push to the connected client.
    console.log(`[WebChat] Response to ${userId}: ${text}`);
  }

  /**
   * End a user's session explicitly (e.g., when the widget is closed).
   */
  async handleEndSession(req: Request, res: Response): Promise<void> {
    const sessionId = req.body.sessionId;
    if (sessionId) {
      await this.sessions.endSession(sessionId);
    }
    res.json({ ok: true });
  }
}
