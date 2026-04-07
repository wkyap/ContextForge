import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface SessionRow {
  thread_id: string;
  checkpoint_count: number;
  latest_checkpoint_id: string;
}

interface SessionsResponse {
  total: number;
  limit: number;
  offset: number;
  sessions: SessionRow[];
}

interface Template {
  name: string;
  description?: string;
  domain?: string;
  type?: string;
}

const DOMAINS = ["industrial", "healthcare", "pharma", "finance", "careerforge"];

export default function AgentChat() {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [domain, setDomain] = useState<string>("industrial");
  const [loading, setLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [templateMode, setTemplateMode] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [templateVars, setTemplateVars] = useState<string>("{}");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Sessions list (uses new /agent/sessions)
  const sessionsQuery = useQuery<SessionsResponse>({
    queryKey: ["agent-sessions"],
    queryFn: () => fetch(`${API}/agent/sessions?limit=30`).then((r) => r.json()),
  });

  // Templates list
  const templatesQuery = useQuery<Template[]>({
    queryKey: ["agent-templates"],
    queryFn: () => fetch(`${API}/agent/templates`).then((r) => r.json()),
  });

  const newChat = () => {
    setMessages([]);
    setThreadId(null);
  };

  const loadSession = (id: string) => {
    setThreadId(id);
    setMessages([
      {
        role: "assistant",
        content:
          `(Resumed thread ${id.slice(0, 8)}… — prior turns are persisted in the LangGraph checkpoint, ` +
          `but not rendered here. New messages will append to this thread.)`,
      },
    ]);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, thread_id: threadId, domain }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setThreadId(data.thread_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response },
      ]);
      queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const runTemplate = async () => {
    if (!selectedTemplate || loading) return;
    let vars: Record<string, unknown>;
    try {
      vars = JSON.parse(templateVars || "{}");
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: variables must be valid JSON." },
      ]);
      return;
    }

    setLoading(true);
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: `[template] ${selectedTemplate}\n${JSON.stringify(vars, null, 2)}`,
      },
    ]);

    try {
      const res = await fetch(
        `${API}/agent/templates/${encodeURIComponent(selectedTemplate)}/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            variables: vars,
            thread_id: threadId,
            domain,
          }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setThreadId(data.thread_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response },
      ]);
      queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const templates = (templatesQuery.data ?? []).filter(
    (t) => !t.type || t.type === "template",
  );

  return (
    <div className="flex h-full">
      {/* Sidebar: sessions + templates */}
      {showSidebar && (
        <aside className="w-72 border-r border-gray-200 bg-gray-50 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-gray-200 space-y-2">
            <button
              onClick={newChat}
              className="w-full rounded-md bg-brand-600 px-3 py-2 text-xs font-medium text-white hover:bg-brand-700"
            >
              + New chat
            </button>
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs"
            >
              {DOMAINS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={templateMode}
                onChange={(e) => setTemplateMode(e.target.checked)}
              />
              Template mode
            </label>
          </div>

          {templateMode && (
            <div className="p-3 border-b border-gray-200 space-y-2">
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                Templates
              </p>
              {templatesQuery.isLoading ? (
                <p className="text-xs text-gray-400">Loading...</p>
              ) : templates.length === 0 ? (
                <p className="text-xs text-gray-400">No templates available.</p>
              ) : (
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs"
                >
                  <option value="">— select template —</option>
                  {templates.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name}
                    </option>
                  ))}
                </select>
              )}
              <textarea
                value={templateVars}
                onChange={(e) => setTemplateVars(e.target.value)}
                placeholder='{"key": "value"}'
                className="w-full h-20 rounded border border-gray-300 p-2 text-xs font-mono"
              />
              <button
                onClick={runTemplate}
                disabled={!selectedTemplate || loading}
                className="w-full rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
              >
                Run template
              </button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            <p className="px-3 pt-3 pb-1 text-xs font-semibold text-gray-700 uppercase tracking-wide">
              Recent sessions
            </p>
            {sessionsQuery.isLoading ? (
              <p className="px-3 text-xs text-gray-400">Loading...</p>
            ) : (sessionsQuery.data?.sessions.length ?? 0) === 0 ? (
              <p className="px-3 text-xs text-gray-400">No sessions yet.</p>
            ) : (
              <ul className="space-y-0.5">
                {sessionsQuery.data?.sessions.map((s) => (
                  <li key={s.thread_id}>
                    <button
                      onClick={() => loadSession(s.thread_id)}
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 ${
                        threadId === s.thread_id
                          ? "bg-brand-50 border-l-2 border-brand-500"
                          : ""
                      }`}
                    >
                      <div className="font-mono truncate text-gray-700">
                        {s.thread_id.slice(0, 16)}…
                      </div>
                      <div className="text-gray-400">
                        {s.checkpoint_count} checkpoint(s)
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      )}

      {/* Main chat */}
      <div className="flex flex-1 flex-col">
        <div className="border-b border-gray-200 bg-white px-4 py-2 flex items-center gap-3">
          <button
            onClick={() => setShowSidebar((s) => !s)}
            className="text-xs text-gray-600 hover:text-gray-900"
          >
            {showSidebar ? "‹ hide" : "› show"}
          </button>
          <span className="text-xs text-gray-400">
            {threadId
              ? `thread ${threadId.slice(0, 12)}… · domain ${domain}`
              : `new thread · domain ${domain}`}
          </span>
        </div>

        <div className="flex-1 overflow-auto p-6 space-y-4 bg-gray-50">
          {messages.length === 0 && (
            <p className="text-center text-gray-400 mt-20">
              Send a message to start chatting with ContextForge.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-2xl rounded-lg px-4 py-3 text-sm whitespace-pre-wrap ${
                m.role === "user"
                  ? "ml-auto bg-brand-500 text-white"
                  : "mr-auto bg-white border border-gray-200 text-gray-800"
              }`}
            >
              {m.content}
            </div>
          ))}
          {loading && (
            <div className="mr-auto text-sm text-gray-400 animate-pulse">
              Thinking...
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="border-t border-gray-200 bg-white p-4 flex gap-3"
        >
          <input
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
