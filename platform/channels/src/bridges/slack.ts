/**
 * Slack Bridge — Slack Events API pattern.
 */

import { Request, Response } from "express";
import { SessionManager } from "../session";
import { MessageNormalizer, NormalizedMessage } from "../normalizer";

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";
const SLACK_BOT_TOKEN = process.env.SLACK_BOT_TOKEN || "";
const SLACK_SIGNING_SECRET = process.env.SLACK_SIGNING_SECRET || "";

export class SlackBridge {
  private sessions: SessionManager;
  private normalizer: MessageNormalizer;

  constructor(sessions: SessionManager, normalizer: MessageNormalizer) {
    this.sessions = sessions;
    this.normalizer = normalizer;
  }

  /**
   * Handle Slack Events API webhook.
   * Supports URL verification, message events, and app mentions.
   */
  async handleWebhook(req: Request, res: Response): Promise<void> {
    const body = req.body;

    // Slack URL verification challenge
    if (body.type === "url_verification") {
      res.json({ challenge: body.challenge });
      return;
    }

    // Acknowledge immediately to meet Slack's 3-second timeout
    res.sendStatus(200);

    const event = body.event;
    if (!event) return;

    // Ignore bot messages and message subtypes (edits, deletes, etc.)
    if (event.bot_id || event.subtype) return;

    // Handle regular messages and app_mention events
    if (event.type === "message" || event.type === "app_mention") {
      const userId = event.user;
      const session = await this.sessions.getOrCreateSession("slack", userId);
      const normalized = this.normalizer.normalize("slack", event, session.id);

      try {
        const reply = await this.forwardToEngine(normalized, session.threadId);
        await this.sendResponse(event.channel, reply, event.thread_ts || event.ts);
      } catch (err) {
        console.error("[Slack] Error processing message:", err);
      }
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

  /** Post a reply to a Slack channel using chat.postMessage. */
  async sendResponse(
    channel: string,
    text: string,
    threadTs?: string,
  ): Promise<void> {
    await fetch("https://slack.com/api/chat.postMessage", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${SLACK_BOT_TOKEN}`,
      },
      body: JSON.stringify({
        channel,
        text,
        thread_ts: threadTs,
      }),
    });
  }
}
