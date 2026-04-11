import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

interface Specialist {
  id: string;
  name: string;
  description: string;
  category: string;
}

interface GuardrailOption {
  id: string;
  name: string;
  description: string;
}

interface ModelTier {
  id: string;
  name: string;
  description: string;
}

interface Catalog {
  specialists: Specialist[];
  guardrails: GuardrailOption[];
  model_tiers: ModelTier[];
}

interface AgentConfig {
  id: string;
  name: string;
  description: string;
  domain: string;
  model_tier: string;
  specialists: string[];
  guardrails: Record<string, boolean>;
  budget_limit: number;
  max_iterations: number;
  is_default: boolean;
  created_at: string;
}

interface ConfigForm {
  name: string;
  description: string;
  domain: string;
  model_tier: string;
  specialists: string[];
  guardrails: Record<string, boolean>;
  budget_limit: number;
  max_iterations: number;
}

const EMPTY_FORM: ConfigForm = {
  name: "",
  description: "",
  domain: "industrial",
  model_tier: "medium",
  specialists: ["retrieval", "analysis", "action"],
  guardrails: { pii: true, toxicity: true, hallucination: true },
  budget_limit: 5.0,
  max_iterations: 15,
};

function tierBadge(tier: string) {
  const colors: Record<string, string> = {
    small: "bg-green-100 text-green-700",
    medium: "bg-blue-100 text-blue-700",
    large: "bg-purple-100 text-purple-700",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[tier] ?? "bg-gray-100 text-gray-600"}`}>
      {tier}
    </span>
  );
}

export default function AgentBuilder() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ConfigForm>({ ...EMPTY_FORM });
  const [selected, setSelected] = useState<AgentConfig | null>(null);

  const { data: catalog } = useQuery<Catalog>({
    queryKey: ["agent-catalog"],
    queryFn: () => fetch(`${API}/agent/configs/catalog`).then((r) => r.json()),
  });

  const { data: configsData } = useQuery<{ configs: AgentConfig[] }>({
    queryKey: ["agent-configs"],
    queryFn: () => fetch(`${API}/agent/configs`).then((r) => r.json()),
  });

  const createMut = useMutation({
    mutationFn: (body: ConfigForm) =>
      fetch(`${API}/agent/configs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then((r) => {
        if (!r.ok) throw new Error("Create failed");
        return r.json();
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent-configs"] });
      setShowForm(false);
      setForm({ ...EMPTY_FORM });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) =>
      fetch(`${API}/agent/configs/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent-configs"] });
      setSelected(null);
    },
  });

  const configs = configsData?.configs ?? [];
  const specialists = catalog?.specialists ?? [];
  const guardrails = catalog?.guardrails ?? [];
  const modelTiers = catalog?.model_tiers ?? [];

  const toggleSpecialist = (id: string) => {
    setForm((f) => ({
      ...f,
      specialists: f.specialists.includes(id)
        ? f.specialists.filter((s) => s !== id)
        : [...f.specialists, id],
    }));
  };

  const toggleGuardrail = (id: string) => {
    setForm((f) => ({
      ...f,
      guardrails: { ...f.guardrails, [id]: !f.guardrails[id] },
    }));
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Builder</h1>
          <p className="text-sm text-gray-500 mt-1">
            Compose custom agent configurations from specialists, guardrails, and model tiers
          </p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setSelected(null); }}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition"
        >
          {showForm ? "Cancel" : "+ New Config"}
        </button>
      </div>

      {/* Builder form */}
      {showForm && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2 className="font-semibold text-gray-900">New Agent Configuration</h2>
          </div>
          <div className="p-6 space-y-6">
            {/* Name + Description */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. industrial-default"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Domain</label>
                <input
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  value={form.domain}
                  onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="What is this agent configuration for?"
              />
            </div>

            {/* Model tier */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Model Tier</label>
              <div className="grid grid-cols-3 gap-3">
                {modelTiers.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setForm((f) => ({ ...f, model_tier: t.id }))}
                    className={`rounded-lg border-2 p-3 text-left transition ${
                      form.model_tier === t.id
                        ? "border-brand-500 bg-brand-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="text-sm font-medium text-gray-900">{t.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Specialists */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Specialists</label>
              <div className="grid grid-cols-3 gap-3">
                {specialists.map((s) => {
                  const active = form.specialists.includes(s.id);
                  return (
                    <button
                      key={s.id}
                      onClick={() => toggleSpecialist(s.id)}
                      className={`rounded-lg border-2 p-3 text-left transition ${
                        active
                          ? "border-brand-500 bg-brand-50"
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${active ? "bg-brand-500" : "bg-gray-300"}`} />
                        <span className="text-sm font-medium text-gray-900">{s.name}</span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">{s.description}</div>
                      <span className="mt-2 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 uppercase">
                        {s.category}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Guardrails */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Guardrails</label>
              <div className="flex flex-wrap gap-3">
                {guardrails.map((g) => {
                  const active = form.guardrails[g.id] ?? false;
                  return (
                    <button
                      key={g.id}
                      onClick={() => toggleGuardrail(g.id)}
                      className={`rounded-lg border px-4 py-2 text-sm transition ${
                        active
                          ? "border-green-300 bg-green-50 text-green-700"
                          : "border-gray-200 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      <span className="font-medium">{g.name}</span>
                      <span className="ml-2 text-xs">{active ? "ON" : "OFF"}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Budget + Iterations */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Budget Limit ($)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  value={form.budget_limit}
                  onChange={(e) => setForm((f) => ({ ...f, budget_limit: parseFloat(e.target.value) || 5 }))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Iterations</label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  value={form.max_iterations}
                  onChange={(e) => setForm((f) => ({ ...f, max_iterations: parseInt(e.target.value) || 15 }))}
                />
              </div>
            </div>

            {/* Graph preview */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Graph Preview</label>
              <div className="rounded-lg bg-gray-50 border border-gray-200 p-4 font-mono text-xs text-gray-600">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="rounded bg-yellow-100 px-2 py-1 text-yellow-800">budget_check</span>
                  <span className="text-gray-400">&rarr;</span>
                  <span className="rounded bg-yellow-100 px-2 py-1 text-yellow-800">context_check</span>
                  <span className="text-gray-400">&rarr;</span>
                  <span className="rounded bg-blue-100 px-2 py-1 text-blue-800">orchestrator</span>
                  <span className="text-gray-400">&rarr;</span>
                  {form.specialists.map((s, i) => (
                    <span key={s}>
                      {i > 0 && <span className="text-gray-400 mx-1">|</span>}
                      <span className="rounded bg-brand-100 px-2 py-1 text-brand-800">{s}</span>
                    </span>
                  ))}
                  <span className="text-gray-400">&rarr;</span>
                  <span className="rounded bg-green-100 px-2 py-1 text-green-800">guardrails</span>
                  <span className="text-gray-400">&rarr;</span>
                  <span className="rounded bg-gray-200 px-2 py-1 text-gray-600">END</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => createMut.mutate(form)}
                disabled={!form.name || form.specialists.length === 0 || createMut.isPending}
                className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
              >
                {createMut.isPending ? "Saving..." : "Save Configuration"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Configs list */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {configs.map((c) => (
          <div
            key={c.id}
            onClick={() => setSelected(selected?.id === c.id ? null : c)}
            className={`cursor-pointer rounded-xl border bg-white p-5 transition hover:shadow-md ${
              selected?.id === c.id ? "border-brand-400 ring-1 ring-brand-200" : "border-gray-200"
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">{c.name}</h3>
                <p className="text-xs text-gray-500 mt-0.5">{c.description || "No description"}</p>
              </div>
              <div className="flex items-center gap-1.5">
                {c.is_default && (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                    DEFAULT
                  </span>
                )}
                {tierBadge(c.model_tier)}
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-1">
              {(c.specialists as string[]).map((s) => (
                <span key={s} className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">
                  {s}
                </span>
              ))}
            </div>

            <div className="mt-2 flex flex-wrap gap-1">
              {Object.entries(c.guardrails as Record<string, boolean>)
                .filter(([, v]) => v)
                .map(([k]) => (
                  <span key={k} className="rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-600">
                    {k}
                  </span>
                ))}
            </div>

            <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
              <span>Domain: {c.domain}</span>
              <span>Budget: ${c.budget_limit}</span>
              <span>Iters: {c.max_iterations}</span>
            </div>
          </div>
        ))}
        {configs.length === 0 && !showForm && (
          <div className="col-span-full text-center py-12 text-gray-400">
            No agent configurations yet. Click "+ New Config" to create one.
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">{selected.name}</h2>
            <button
              onClick={() => deleteMut.mutate(selected.id)}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 transition"
            >
              Delete
            </button>
          </div>
          <pre className="rounded-lg bg-gray-50 p-4 text-xs text-gray-700 overflow-auto max-h-80">
            {JSON.stringify(selected, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
