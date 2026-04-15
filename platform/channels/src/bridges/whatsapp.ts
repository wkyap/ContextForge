/**
 * WhatsApp Bridge — Meta Cloud API webhook pattern.
 */

import { Request, Response } from "express";
import { SessionManager } from "../session";
import { MessageNormalizer, NormalizedMessage } from "../normalizer";

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN || "";
const WHATSAPP_VERIFY_TOKEN = process.env.WHATSAPP_VERIFY_TOKEN || "";
const WHATSAPP_PHONE_ID = process.env.WHATSAPP_PHONE_ID || "";

export class WhatsAppBridge {
  private sessions: SessionManager;
  private normalizer: MessageNormalizer;

  constructor(sessions: SessionManager, normalizer: MessageNormalizer) {
    this.sessions = sessions;
    this.normalizer = normalizer;
  }

  /**
   * Handle incoming Meta Cloud API webhook (POST).
   * Processes messages from WhatsApp and forwards to ContextForge engine.
   */
  async handleWebhook(req: Request, res: Response): Promise<void> {
    const body = req.body;

    // Meta sends a structured payload with entries
    const entry = body.entry?.[0];
    const change = entry?.changes?.[0];
    const value = change?.value;
    const message = value?.messages?.[0];

    if (!message) {
      res.sendStatus(200);
      return;
    }

    const from = message.from; // phone number
    const session = await this.sessions.getOrCreateSession("whatsapp", from);
    const normalized = this.normalizer.normalize("whatsapp", message, session.id);

    try {
      const reply = await this.forwardToEngine(normalized, session.threadId);
      await this.sendResponse(from, reply);
      res.sendStatus(200);
    } catch (err) {
      console.error("[WhatsApp] Error processing message:", err);
      res.sendStatus(500);
    }
  }

  /**
   * Handle Meta webhook verification (GET).
   */
  handleVerification(req: Request, res: Response): void {
    const mode = req.query["hub.mode"];
    const token = req.query["hub.verify_token"];
    const challenge = req.query["hub.challenge"];

    if (mode === "subscribe" && token === WHATSAPP_VERIFY_TOKEN) {
      res.status(200).send(challenge);
    } else {
      res.sendStatus(403);
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

  /** Send a text reply via Meta Cloud API. */
  async sendResponse(to: string, text: string): Promise<void> {
    await fetch(
      `https://graph.facebook.com/v18.0/${WHATSAPP_PHONE_ID}/messages`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${WHATSAPP_TOKEN}`,
        },
        body: JSON.stringify({
          messaging_product: "whatsapp",
          to,
          type: "text",
          text: { body: text },
        }),
      },
    );
  }
}
