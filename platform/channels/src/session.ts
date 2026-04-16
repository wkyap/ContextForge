/**
 * Session Manager — maps external user IDs to ContextForge thread_ids.
 */

import { randomUUID } from "crypto";

export interface Session {
  id: string;
  threadId: string;
  platform: string;
  externalUserId: string;
  createdAt: Date;
  lastActiveAt: Date;
}

const DEFAULT_TTL_MS = 30 * 60 * 1000; // 30 minutes

export class SessionManager {
  private sessions = new Map<string, Session>();
  private ttlMs: number;
  private cleanupTimer: ReturnType<typeof setInterval>;

  constructor(ttlMs: number = DEFAULT_TTL_MS) {
    this.ttlMs = ttlMs;
    this.cleanupTimer = setInterval(() => this.cleanup(), this.ttlMs);
  }

  /** Build a lookup key from platform + external user ID. */
  private key(platform: string, externalId: string): string {
    return `${platform}:${externalId}`;
  }

  /** Return an existing session or create a new one. */
  async getOrCreateSession(
    platform: string,
    externalId: string,
  ): Promise<Session> {
    const k = this.key(platform, externalId);
    const existing = this.sessions.get(k);

    if (existing) {
      existing.lastActiveAt = new Date();
      return existing;
    }

    const session: Session = {
      id: randomUUID(),
      threadId: `${platform}:${externalId}:${randomUUID()}`,
      platform,
      externalUserId: externalId,
      createdAt: new Date(),
      lastActiveAt: new Date(),
    };

    this.sessions.set(k, session);
    return session;
  }

  /** End a session by its session ID. */
  async endSession(sessionId: string): Promise<void> {
    for (const [key, session] of this.sessions) {
      if (session.id === sessionId) {
        this.sessions.delete(key);
        return;
      }
    }
  }

  /** Remove sessions that have exceeded the TTL. */
  private cleanup(): void {
    const now = Date.now();
    for (const [key, session] of this.sessions) {
      if (now - session.lastActiveAt.getTime() > this.ttlMs) {
        this.sessions.delete(key);
      }
    }
  }

  /** Stop the background cleanup timer (useful for tests / shutdown). */
  destroy(): void {
    clearInterval(this.cleanupTimer);
  }
}
