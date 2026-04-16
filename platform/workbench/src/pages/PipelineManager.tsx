import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

interface Pipeline {
  id: string;
  name: string;
  description: string | null;
  type: string;
  domain: string | null;
  enabled: boolean;
  schedule_cron: string | null;
  last_run_at: string | null;
  last_run_status: string | null;
  error_count_24h: number;
  records_processed_24h: number;
  created_at: string;
}

interface PipelineRun {
  id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  records_processed: number | null;
  error_count: number | null;
  error_message: string | null;
}

interface CreateForm {
  name: string;
  type: string;
  domain: string;
  description: string;
  schedule_cron: string;
}

const EMPTY_FORM: CreateForm = {
  name: "",
  type: "document",
  domain: "",
  description: "",
  schedule_cron: "",
};

function statusBadge(status: string | null) {
  const s = status ?? "idle";
  const cls =
    s === "running"
      ? "bg-blue-100 text-blue-700"
      : s === "success"
        ? "bg-green-100 text-green-700"
        : s === "failure"
          ? "bg-red-100 text-red-700"
          : "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {s}
    </span>
  );
}

export default function PipelineManager() {
  const queryClient = useQueryClient();
  const [domainFilter, setDomainFilter] = useState<string>("");
  const [enabledFilter, setEnabledFilter] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const pipelinesQuery = useQuery<{ count: number; pipelines: Pipeline[] }>({
    queryKey: ["pipelines", domainFilter, enabledFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (domainFilter) params.set("domain", domainFilter);
      if (enabledFilter) params.set("enabled", enabledFilter);
      params.set("limit", "100");
      return fetch(`${API}/pipelines?${params}`).then((r) => r.json());
    },
  });

  const runsQuery = useQuery<{ count: number; runs: PipelineRun[] }>({
    queryKey: ["pipeline-runs", selectedId],
    queryFn: () =>
      fetch(`${API}/pipelines/${selectedId}/runs?limit=20`).then((r) => r.json()),
    enabled: !!selectedId,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        type: form.type,
        domain: form.domain || null,
        description: form.description,
        schedule_cron: form.schedule_cron || null,
        config: {},
      };
      const res = await fetch(`${API}/pipelines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Create failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      setShowCreate(false);
      setForm(EMPTY_FORM);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["pipelines"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const triggerMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${API}/pipelines/${id}/trigger`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Trigger failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] });
      queryClient.invalidateQueries({ queryKey: ["pipeline-runs", id] });
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${API}/pipelines/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      setSelectedId(null);
      queryClient.invalidateQueries({ queryKey: ["pipelines"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      const res = await fetch(`${API}/pipelines/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error(`Update failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pipelines"] }),
    onError: (e: Error) => setError(e.message),
  });

  const pipelines = pipelinesQuery.data?.pipelines ?? [];
  const selected = pipelines.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pipeline Manager</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage ingestion pipelines, trigger runs, and inspect run history.
          </p>
        </div>
        <button
          onClick={() => setShowCreate((s) => !s)}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {showCreate ? "Cancel" : "+ New Pipeline"}
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <section className="rounded-lg border border-gray-200 bg-white p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-800">Create pipeline</h2>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="document">document</option>
              <option value="api">api</option>
              <option value="stream">stream</option>
              <option value="batch">batch</option>
            </select>
            <input
              placeholder="Domain (optional)"
              value={form.domain}
              onChange={(e) => setForm({ ...form, domain: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <input
              placeholder="Schedule cron (optional)"
              value={form.schedule_cron}
              onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm font-mono"
            />
            <input
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="col-span-2 rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!form.name || createMutation.isPending}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {createMutation.isPending ? "Creating..." : "Create"}
          </button>
        </section>
      )}

      {/* Filters */}
      <div className="flex gap-3 items-center text-sm">
        <input
          placeholder="Filter by domain"
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className="rounded border border-gray-300 px-3 py-1.5"
        />
        <select
          value={enabledFilter}
          onChange={(e) => setEnabledFilter(e.target.value)}
          className="rounded border border-gray-300 px-3 py-1.5"
        >
          <option value="">All</option>
          <option value="true">Enabled only</option>
          <option value="false">Disabled only</option>
        </select>
        <span className="text-gray-400">
          {pipelinesQuery.data?.count ?? 0} pipeline(s)
        </span>
      </div>

      {/* Pipeline list */}
      <section>
        {pipelinesQuery.isLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading...</p>
        ) : pipelines.length === 0 ? (
          <p className="text-sm text-gray-400">No pipelines match these filters.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Type</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Domain</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">
                    Records / 24h
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">
                    Errors / 24h
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">
                    Last Run
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {pipelines.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => setSelectedId(p.id)}
                    className={`cursor-pointer hover:bg-gray-50 ${
                      selectedId === p.id ? "bg-brand-50" : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-medium text-gray-900">{p.name}</td>
                    <td className="px-4 py-3 text-gray-600">{p.type}</td>
                    <td className="px-4 py-3 text-gray-600">{p.domain ?? "--"}</td>
                    <td className="px-4 py-3">
                      {p.enabled ? statusBadge(p.last_run_status) : statusBadge("disabled")}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{p.records_processed_24h}</td>
                    <td
                      className={`px-4 py-3 ${p.error_count_24h > 0 ? "text-red-600 font-medium" : "text-gray-600"}`}
                    >
                      {p.error_count_24h}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {p.last_run_at ? new Date(p.last_run_at).toLocaleString() : "--"}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerMutation.mutate(p.id);
                        }}
                        disabled={!p.enabled || p.last_run_status === "running"}
                        className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-40"
                      >
                        Trigger
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleMutation.mutate({ id: p.id, enabled: !p.enabled });
                        }}
                        className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      >
                        {p.enabled ? "Disable" : "Enable"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Run history for selected */}
      {selected && (
        <section className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-gray-800">
                Recent runs — {selected.name}
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                {selected.schedule_cron
                  ? `Schedule: ${selected.schedule_cron}`
                  : "No schedule (manual trigger only)"}
              </p>
            </div>
            <button
              onClick={() => {
                if (confirm(`Delete pipeline "${selected.name}"?`)) {
                  deleteMutation.mutate(selected.id);
                }
              }}
              className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
            >
              Delete
            </button>
          </div>
          {runsQuery.isLoading ? (
            <p className="text-sm text-gray-400 animate-pulse">Loading runs...</p>
          ) : (runsQuery.data?.runs.length ?? 0) === 0 ? (
            <p className="text-sm text-gray-400">No runs yet.</p>
          ) : (
            <table className="min-w-full text-xs">
              <thead className="text-gray-500">
                <tr>
                  <th className="px-2 py-1 text-left">Status</th>
                  <th className="px-2 py-1 text-left">Started</th>
                  <th className="px-2 py-1 text-left">Completed</th>
                  <th className="px-2 py-1 text-left">Records</th>
                  <th className="px-2 py-1 text-left">Errors</th>
                  <th className="px-2 py-1 text-left">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runsQuery.data?.runs.map((r) => (
                  <tr key={r.id}>
                    <td className="px-2 py-1.5">{statusBadge(r.status)}</td>
                    <td className="px-2 py-1.5 text-gray-600">
                      {new Date(r.started_at).toLocaleString()}
                    </td>
                    <td className="px-2 py-1.5 text-gray-600">
                      {r.completed_at ? new Date(r.completed_at).toLocaleString() : "--"}
                    </td>
                    <td className="px-2 py-1.5 text-gray-600">
                      {r.records_processed ?? "--"}
                    </td>
                    <td
                      className={`px-2 py-1.5 ${(r.error_count ?? 0) > 0 ? "text-red-600 font-medium" : "text-gray-600"}`}
                    >
                      {r.error_count ?? 0}
                    </td>
                    <td className="px-2 py-1.5 text-gray-500 truncate max-w-md">
                      {r.error_message ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}
