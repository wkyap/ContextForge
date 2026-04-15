/**
 * Message Normalizer — converts platform-specific messages to a unified format.
 */

export interface Attachment {
  type: "image" | "voice" | "file" | "video";
  url?: string;
  mimeType?: string;
  filename?: string;
}

export interface NormalizedMessage {
  text: string;
  platform: string;
  userId: string;
  sessionId: string;
  attachments: Attachment[];
  metadata: Record<string, unknown>;
}

export class MessageNormalizer {
  /**
   * Convert a raw platform-specific message into a NormalizedMessage.
   */
  normalize(
    platform: string,
    rawMessage: any,
    sessionId: string = "",
  ): NormalizedMessage {
    switch (platform) {
      case "whatsapp":
        return this.normalizeWhatsApp(rawMessage, sessionId);
      case "slack":
        return this.normalizeSlack(rawMessage, sessionId);
      case "teams":
        return this.normalizeTeams(rawMessage, sessionId);
      case "telegram":
        return this.normalizeTelegram(rawMessage, sessionId);
      case "discord":
        return this.normalizeDiscord(rawMessage, sessionId);
      case "webchat":
        return this.normalizeWebChat(rawMessage, sessionId);
      default:
        return this.normalizeGeneric(platform, rawMessage, sessionId);
    }
  }

  private normalizeWhatsApp(raw: any, sessionId: string): NormalizedMessage {
    const attachments: Attachment[] = [];
    if (raw.image) {
      attachments.push({ type: "image", url: raw.image.id, mimeType: raw.image.mime_type });
    }
    if (raw.voice) {
      attachments.push({ type: "voice", url: raw.voice.id, mimeType: raw.voice.mime_type });
    }
    return {
      text: raw.text?.body || raw.body || "",
      platform: "whatsapp",
      userId: raw.from || "",
      sessionId,
      attachments,
      metadata: { messageId: raw.id, timestamp: raw.timestamp },
    };
  }

  private normalizeSlack(raw: any, sessionId: string): NormalizedMessage {
    const attachments: Attachment[] = (raw.files || []).map((f: any) => ({
      type: f.mimetype?.startsWith("image/") ? "image" : "file",
      url: f.url_private,
      mimeType: f.mimetype,
      filename: f.name,
    }));
    return {
      text: raw.text || "",
      platform: "slack",
      userId: raw.user || "",
      sessionId,
      attachments,
      metadata: { channel: raw.channel, ts: raw.ts, threadTs: raw.thread_ts },
    };
  }

  private normalizeTeams(raw: any, sessionId: string): NormalizedMessage {
    const attachments: Attachment[] = (raw.attachments || []).map((a: any) => ({
      type: a.contentType?.startsWith("image/") ? "image" : "file",
      url: a.contentUrl,
      mimeType: a.contentType,
      filename: a.name,
    }));
    return {
      text: raw.text || "",
      platform: "teams",
      userId: raw.from?.id || "",
      sessionId,
      attachments,
      metadata: { conversationId: raw.conversation?.id, activityId: raw.id },
    };
  }

  private normalizeTelegram(raw: any, sessionId: string): NormalizedMessage {
    const attachments: Attachment[] = [];
    if (raw.photo) {
      const largest = raw.photo[raw.photo.length - 1];
      attachments.push({ type: "image", url: largest?.file_id });
    }
    if (raw.voice) {
      attachments.push({ type: "voice", url: raw.voice.file_id, mimeType: raw.voice.mime_type });
    }
    return {
      text: raw.text || raw.caption || "",
      platform: "telegram",
      userId: String(raw.from?.id || ""),
      sessionId,
      attachments,
      metadata: { chatId: raw.chat?.id, messageId: raw.message_id },
    };
  }

  private normalizeDiscord(raw: any, sessionId: string): NormalizedMessage {
    const attachments: Attachment[] = (raw.attachments || []).map((a: any) => ({
      type: a.content_type?.startsWith("image/") ? "image" : "file",
      url: a.url,
      mimeType: a.content_type,
      filename: a.filename,
    }));
    return {
      text: raw.content || "",
      platform: "discord",
      userId: raw.author?.id || "",
      sessionId,
      attachments,
      metadata: { channelId: raw.channel_id, guildId: raw.guild_id },
    };
  }

  private normalizeWebChat(raw: any, sessionId: string): NormalizedMessage {
    const attachments: Attachment[] = (raw.attachments || []).map((a: any) => ({
      type: a.type || "file",
      url: a.url,
      mimeType: a.mimeType,
      filename: a.filename,
    }));
    return {
      text: raw.text || raw.message || "",
      platform: "webchat",
      userId: raw.userId || raw.user_id || "",
      sessionId,
      attachments,
      metadata: raw.metadata || {},
    };
  }

  private normalizeGeneric(
    platform: string,
    raw: any,
    sessionId: string,
  ): NormalizedMessage {
    return {
      text: raw.text || raw.message || raw.body || "",
      platform,
      userId: raw.userId || raw.user_id || raw.from || "",
      sessionId,
      attachments: [],
      metadata: raw.metadata || {},
    };
  }
}
