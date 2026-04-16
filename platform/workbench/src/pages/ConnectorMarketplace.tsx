import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

interface DriversResponse {
  drivers: string[];
}

interface SinksResponse {
  sinks: string[];
}

interface RunningEntry {
  name: string;
  source_kind: string;
  health: {
    status: string;
    records_emitted: number;
    last_record_at: number | null;
    last_error: string | null;
  };
}

interface RunningResponse {
  running: RunningEntry[];
}

interface PersistedConfig {
  name: string;
  source_kind: string;
  config: Record<string, unknown>;
  sink: string | null;
  enabled: boolean;
  description: string | null;
}

interface ConfigsResponse {
  configs: PersistedConfig[];
}

interface NewConfigForm {
  name: string;
  source_kind: string;
  sink: string;
  description: string;
  config_json: string;
  enabled: boolean;
}

const EMPTY_FORM: NewConfigForm = {
  name: "",
  source_kind: "",
  sink: "",
  description: "",
  config_json: "{}",
  enabled: true,
};

function statusBadge(status: string) {
  const cls =
    status === "running"
      ? "bg-green-100 text-green-700"
      : status === "starting"
        ? "bg-blue-100 text-blue-700"
        : status === "error"
          ? "bg-red-100 text-red-700"
          : status === "stopped" || status === "stopping"
            ? "bg-gray-200 text-gray-700"
            : "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export default function ConnectorMarketplace() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<NewConfigForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const driversQuery = useQuery<DriversResponse>({
    queryKey: ["connector-drivers"],
    queryFn: () => fetch(`${API}/connectors/drivers`).then((r) => r.json()),
  });

  const sinksQuery = useQuery<SinksResponse>({
    queryKey: ["connector-sinks"],
    queryFn: () => fetch(`${API}/connectors/sinks`).then((r) => r.json()),
  });

  const runningQuery = useQuery<RunningResponse>({
    queryKey: ["connector-running"],
    queryFn: () => fetch(`${API}/connectors`).then((r) => r.json()),
    refetchInterval: 5000,
  });

  const configsQuery = useQuery<ConfigsResponse>({
    queryKey: ["connector-configs"],
    queryFn: () => fetch(`${API}/connectors/configs`).then((r) => r.json()),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["connector-running"] });
    queryClient.invalidateQueries({ queryKey: ["connector-configs"] });
  };

  const upsertMutation = useMutation({
    mutationFn: async () => {
      let parsed: Record<string, unknown> = {};
      try {
        parsed = JSON.parse(form.config_json || "{}");
      } catch (e) {
        throw new Error(`Invalid JSON in config: ${(e as Error).message}`);
      }
      const body = {
        name: form.name,
        source_kind: form.source_kind,
        sink: form.sink || null,
        description: form.description || null,
        config: parsed,
        enabled: form.enabled,
      };
      const res = await fetch(`${API}/connectors/configs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Save failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      setShowCreate(false);
      setForm(EMPTY_FORM);
      setError(null);
      invalidateAll();
    },
    onError: (e: Error) => setError(e.message),
  });

  const startConfigMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch(`${API}/connectors/configs/${name}/start`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Start failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: invalidateAll,
    onError: (e: Error) => setError(e.message),
  });

  const stopMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch(`${API}/connectors/${name}/stop`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Stop failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: invalidateAll,
    onError: (e: Error) => setError(e.message),
  });

  const deleteConfigMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch(`${API}/connectors/configs/${name}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Delete failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: invalidateAll,
    onError: (e: Error) => setError(e.message),
  });

  const drivers = driversQuery.data?.drivers ?? [];
  const sinks = sinksQuery.data?.sinks ?? [];
  const running = runningQuery.data?.running ?? [];
  const configs = configsQuery.data?.configs ?? [];
  const runningByName = new Map(running.map((r) => [r.name, r]));

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Connector Marketplace</h1>
          <p className="text-sm text-gray-500 mt-1">
            Browse drivers, configure connectors, and supervise running streams.
          </p>
        </div>
        <button
          onClick={() => setShowCreate((s) => !s)}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {showCreate ? "Cancel" : "+ New Config"}
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Available drivers */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-800 mb-3">Available drivers</h2>
        {driversQuery.isLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : drivers.length === 0 ? (
          <p className="text-sm text-gray-400">No drivers registered.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {drivers.map((d) => (
              <span
                key={d}
                className="rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-mono text-brand-700"
              >
                {d}
              </span>
            ))}
          </div>
        )}
        <div className="mt-3 text-xs text-gray-500">
          Sinks available for override:{" "}
          {sinks.length === 0 ? (
            <span className="text-gray-400">none registered</span>
          ) : (
            sinks.map((s) => (
              <span
                key={s}
                className="ml-1 rounded border border-gray-300 bg-gray-50 px-1.5 py-0.5 font-mono text-gray-700"
              >
                {s}
              </span>
            ))
          )}
        </div>
      </section>

      {/* Create config form */}
      {showCreate && (
        <section className="rounded-lg border border-gray-200 bg-white p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-800">New connector config</h2>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Name (unique)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <select
              value={form.source_kind}
              onChange={(e) => setForm({ ...form, source_kind: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">— select driver —</option>
              {drivers.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              value={form.sink}
              onChange={(e) => setForm({ ...form, sink: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">default sink</option>
              {sinks.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              Enabled (autostart on api boot)
            </label>
            <input
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="col-span-2 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <textarea
              placeholder='Config JSON, e.g. {"url": "https://...", "interval_s": 30}'
              value={form.config_json}
              onChange={(e) => setForm({ ...form, config_json: e.target.value })}
              rows={6}
              className="col-span-2 rounded border border-gray-300 px-3 py-2 text-xs font-mono"
            />
          </div>
          <button
            onClick={() => upsertMutation.mutate()}
            disabled={!form.name || !form.source_kind || upsertMutation.isPending}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {upsertMutation.isPending ? "Saving…" : "Save config"}
          </button>
        </section>
      )}

      {/* Persisted configs */}
      <section>
        <h2 className="text-sm font-semibold text-gray-800 mb-2">Persisted configs</h2>
        {configsQuery.isLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : configs.length === 0 ? (
          <p className="text-sm text-gray-400">No configs yet — create one above.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Driver</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Sink</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Enabled</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Emitted</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {configs.map((c) => {
                  const live = runningByName.get(c.name);
                  const isRunning = !!live && live.health.status === "running";
                  return (
                    <tr key={c.name}>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {c.name}
                        {c.description && (
                          <p className="text-xs text-gray-500 font-normal mt-0.5">
                            {c.description}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">
                        {c.source_kind}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{c.sink ?? "default"}</td>
                      <td className="px-4 py-3">
                        {c.enabled ? (
                          <span className="text-green-700 text-xs font-medium">yes</span>
                        ) : (
                          <span className="text-gray-400 text-xs">no</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {live ? statusBadge(live.health.status) : statusBadge("idle")}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {live?.health.records_emitted ?? 0}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                        {isRunning ? (
                          <button
                            onClick={() => stopMutation.mutate(c.name)}
                            className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                          >
                            Stop
                          </button>
                        ) : (
                          <button
                            onClick={() => startConfigMutation.mutate(c.name)}
                            className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-700"
                          >
                            Start
                          </button>
                        )}
                        <button
                          onClick={() => {
                            if (confirm(`Delete config "${c.name}"?`)) {
                              deleteConfigMutation.mutate(c.name);
                            }
                          }}
                          className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Ad-hoc running connectors (not in configs) */}
      {running.filter((r) => !configs.find((c) => c.name === r.name)).length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-800 mb-2">
            Ad-hoc running (no persisted config)
          </h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Driver</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Emitted</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Last Error</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {running
                  .filter((r) => !configs.find((c) => c.name === r.name))
                  .map((r) => (
                    <tr key={r.name}>
                      <td className="px-4 py-3 font-medium text-gray-900">{r.name}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">
                        {r.source_kind}
                      </td>
                      <td className="px-4 py-3">{statusBadge(r.health.status)}</td>
                      <td className="px-4 py-3 text-gray-600">{r.health.records_emitted}</td>
                      <td className="px-4 py-3 text-xs text-red-600 truncate max-w-md">
                        {r.health.last_error ?? ""}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => stopMutation.mutate(r.name)}
                          className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                        >
                          Stop
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
