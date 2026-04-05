/**
 * Channel Gateway — routes messages from external platforms to ContextForge engine.
 */

import express from "express";

const app = express();
app.use(express.json());

const ENGINE_URL = process.env.ENGINE_URL || "http://localhost:8000";
const PORT = parseInt(process.env.PORT || "3100", 10);

interface IncomingMessage {
  platform: string;
  channel_id: string;
  user_id: string;
  message: string;
  metadata?: Record<string, unknown>;
}

// Generic message handler — forwards to engine API
async function handleMessage(msg: IncomingMessage): Promise<string> {
  const res = await fetch(`${ENGINE_URL}/api/v1/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: msg.message,
      thread_id: `${msg.platform}:${msg.channel_id}:${msg.user_id}`,
    }),
  });
  const data = await res.json();
  return data.response || "Sorry, I could not process that.";
}

// WhatsApp webhook
app.post("/webhook/whatsapp", async (req, res) => {
  const { from, body: text } = req.body;
  const reply = await handleMessage({
    platform: "whatsapp",
    channel_id: from,
    user_id: from,
    message: text,
  });
  res.json({ reply });
});

// Slack events
app.post("/webhook/slack", async (req, res) => {
  // Slack URL verification
  if (req.body.type === "url_verification") {
    return res.json({ challenge: req.body.challenge });
  }

  const event = req.body.event;
  if (event?.type === "message" && !event.bot_id) {
    const reply = await handleMessage({
      platform: "slack",
      channel_id: event.channel,
      user_id: event.user,
      message: event.text,
    });
    // In production, use Slack API to post reply
    console.log(`[Slack] Reply to ${event.channel}: ${reply}`);
  }
  res.sendStatus(200);
});

// Teams webhook
app.post("/webhook/teams", async (req, res) => {
  const { from, text, conversation } = req.body;
  const reply = await handleMessage({
    platform: "teams",
    channel_id: conversation?.id || "unknown",
    user_id: from?.id || "unknown",
    message: text || "",
  });
  res.json({ type: "message", text: reply });
});

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", platform: "channel-gateway" });
});

app.listen(PORT, () => {
  console.log(`Channel gateway listening on port ${PORT}`);
});

export default app;
