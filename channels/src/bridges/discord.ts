/**
 * Discord Bridge — Discord webhook / interactions pattern.
 */

import { Request, Response } from "express";
import { SessionManager } from "../session";
import { MessageNormalizer, NormalizedMessage } from "../normalizer";

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";
const DISCORD_BOT_TOKEN = process.env.DISCORD_BOT_TOKEN || "";
const DISCORD_PUBLIC_KEY = process.env.DISCORD_PUBLIC_KEY || "";

export class DiscordBridge {
  private sessions: SessionManager;
  private normalizer: MessageNormalizer;

  constructor(sessions: SessionManager, normalizer: MessageNormalizer) {
    this.sessions = sessions;
    this.normalizer = normalizer;
  }

  /**
   * Handle Discord webhook / gateway event.
   * Supports interaction verification and message create events.
   */
  async handleWebhook(req: Request, res: Response): Promise<void> {
    const body = req.body;

    // Discord interaction ping verification
    if (body.type === 1) {
      res.json({ type: 1 });
      return;
    }

    // Handle message events (type 0 = channel message with content)
    const message = body.type === 0 ? body : body.d;
    if (!message || !message.content) {
      res.sendStatus(200);
      return;
    }

    // Ignore bot messages
    if (message.author?.bot) {
      res.sendStatus(200);
      return;
    }

    const userId = message.author?.id || "";
    const session = await this.sessions.getOrCreateSession("discord", userId);
    const normalized = this.normalizer.normalize("discord", message, session.id);

    try {
      const reply = await this.forwardToEngine(normalized, session.threadId);
      await this.sendResponse(message.channel_id, reply);
      res.sendStatus(200);
    } catch (err) {
      console.error("[Discord] Error processing message:", err);
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

  /** Send a message to a Discord channel via REST API. */
  async sendResponse(channelId: string, text: string): Promise<void> {
    await fetch(
      `https://discord.com/api/v10/channels/${channelId}/messages`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bot ${DISCORD_BOT_TOKEN}`,
        },
        body: JSON.stringify({ content: text }),
      },
    );
  }
}
