/**
 * Telegram Bridge — Bot API webhook pattern.
 */

import { Request, Response } from "express";
import { SessionManager } from "../session";
import { MessageNormalizer, NormalizedMessage } from "../normalizer";

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";

export class TelegramBridge {
  private sessions: SessionManager;
  private normalizer: MessageNormalizer;

  constructor(sessions: SessionManager, normalizer: MessageNormalizer) {
    this.sessions = sessions;
    this.normalizer = normalizer;
  }

  /**
   * Handle Telegram Bot API webhook update.
   * Processes incoming messages and forwards to ContextForge engine.
   */
  async handleWebhook(req: Request, res: Response): Promise<void> {
    const update = req.body;
    const message = update.message || update.edited_message;

    if (!message) {
      res.sendStatus(200);
      return;
    }

    const userId = String(message.from?.id || "");
    const session = await this.sessions.getOrCreateSession("telegram", userId);
    const normalized = this.normalizer.normalize("telegram", message, session.id);

    try {
      const reply = await this.forwardToEngine(normalized, session.threadId);
      await this.sendResponse(message.chat.id, reply, message.message_id);
      res.sendStatus(200);
    } catch (err) {
      console.error("[Telegram] Error processing message:", err);
      res.sendStatus(500);
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

  /** Send a reply via Telegram Bot API sendMessage. */
  async sendResponse(
    chatId: number | string,
    text: string,
    replyToMessageId?: number,
  ): Promise<void> {
    await fetch(
      `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          reply_to_message_id: replyToMessageId,
          parse_mode: "Markdown",
        }),
      },
    );
  }
}
