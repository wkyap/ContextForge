/**
 * Microsoft Teams Bridge — Bot Framework pattern.
 */

import { Request, Response } from "express";
import { SessionManager } from "../session";
import { MessageNormalizer, NormalizedMessage } from "../normalizer";

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";
const TEAMS_APP_ID = process.env.TEAMS_APP_ID || "";
const TEAMS_APP_PASSWORD = process.env.TEAMS_APP_PASSWORD || "";

export class TeamsBridge {
  private sessions: SessionManager;
  private normalizer: MessageNormalizer;

  constructor(sessions: SessionManager, normalizer: MessageNormalizer) {
    this.sessions = sessions;
    this.normalizer = normalizer;
  }

  /**
   * Handle Bot Framework activity webhook.
   * Processes incoming activities (messages) from Microsoft Teams.
   */
  async handleWebhook(req: Request, res: Response): Promise<void> {
    const activity = req.body;

    // Only handle message activities
    if (activity.type !== "message") {
      res.sendStatus(200);
      return;
    }

    const userId = activity.from?.id || "unknown";
    const session = await this.sessions.getOrCreateSession("teams", userId);
    const normalized = this.normalizer.normalize("teams", activity, session.id);

    try {
      const reply = await this.forwardToEngine(normalized, session.threadId);
      await this.sendResponse(activity, reply);
      res.sendStatus(200);
    } catch (err) {
      console.error("[Teams] Error processing message:", err);
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

  /**
   * Send a reply via Bot Framework.
   * Posts a reply activity back to the conversation using the service URL.
   */
  async sendResponse(
    incomingActivity: any,
    text: string,
  ): Promise<void> {
    const serviceUrl = incomingActivity.serviceUrl;
    const conversationId = incomingActivity.conversation?.id;

    if (!serviceUrl || !conversationId) {
      console.warn("[Teams] Missing serviceUrl or conversationId");
      return;
    }

    const token = await this.getAccessToken();
    const replyUrl = `${serviceUrl}/v3/conversations/${conversationId}/activities/${incomingActivity.id}`;

    await fetch(replyUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        type: "message",
        from: { id: TEAMS_APP_ID, name: "ContextForge" },
        text,
        replyToId: incomingActivity.id,
      }),
    });
  }

  /** Obtain an access token from the Bot Framework token endpoint. */
  private async getAccessToken(): Promise<string> {
    const res = await fetch(
      "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "client_credentials",
          client_id: TEAMS_APP_ID,
          client_secret: TEAMS_APP_PASSWORD,
          scope: "https://api.botframework.com/.default",
        }).toString(),
      },
    );
    const data = await res.json();
    return data.access_token || "";
  }
}
