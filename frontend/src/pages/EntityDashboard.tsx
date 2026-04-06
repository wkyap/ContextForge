import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

const API = "/api/v1";

interface Entity {
  id: string;
  _type: string;
  _version: number;
  _updated_at: string;
  _source_system: string;
  _confidence: number;
  name?: string;
  [key: string]: unknown;
}

interface TelemetryParam {
  parameter: string;
  unit: string;
  first_seen: string;
  last_seen: string;
  total_readings: number;
}

interface TelemetryPoint {
  bucket: string;
  avg_value: number;
  min_value: number;
  max_value: number;
  sample_count: number;
}

export default function EntityDashboard() {
  const [selectedEntity, setSelectedEntity] = useState<string>("");
  const [selectedParam, setSelectedParam] = useState<string>("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");

  // Entities
  const entities = useQuery<{ count: number; entities: Entity[] }>({
    queryKey: ["entities", entityTypeFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "100" });
      if (entityTypeFilter) params.set("entity_type", entityTypeFilter);
      return fetch(`${API}/graph/entities?${params}`).then((r) => r.json());
    },
  });

  // Parameters for selected entity
  const params = useQuery<{ parameters: TelemetryParam[] }>({
    queryKey: ["entity-params", selectedEntity],
    queryFn: () =>
      fetch(`${API}/timeseries/parameters?entity_id=${selectedEntity}`).then(
        (r) => r.json()
      ),
    enabled: !!selectedEntity,
  });

  // Telemetry data
  const telemetry = useQuery<{ data: TelemetryPoint[] }>({
    queryKey: ["entity-telemetry", selectedEntity, selectedParam],
    queryFn: () =>
      fetch(
        `${API}/timeseries/query?entity_id=${selectedEntity}&parameter=${selectedParam}&bucket=1 hour`
      ).then((r) => r.json()),
    enabled: !!selectedEntity && !!selectedParam,
  });

  // Trend data
  const trend = useQuery<{
    data: {
      bucket: string;
      avg_value: number;
      moving_avg_3: number | null;
      delta: number | null;
      pct_change: number | null;
    }[];
  }>({
    queryKey: ["entity-trend", selectedEntity, selectedParam],
    queryFn: () =>
      fetch(
        `${API}/timeseries/trend?entity_id=${selectedEntity}&parameter=${selectedParam}`
      ).then((r) => r.json()),
    enabled: !!selectedEntity && !!selectedParam,
  });

  const entityTypes = [
    ...new Set(
      (entities.data?.entities ?? []).map((e) => e._type).filter(Boolean)
    ),
  ];

  // Stats for overview cards
  const entityList = entities.data?.entities ?? [];
  const typeCount = entityTypes.length;
  const avgConfidence =
    entityList.length > 0
      ? entityList.reduce((sum, e) => sum + (e._confidence ?? 1), 0) /
        entityList.length
      : 0;
  const sourceSystems = [
    ...new Set(entityList.map((e) => e._source_system).filter(Boolean)),
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Entity Dashboard</h1>
        <p className="text-sm text-gray-400 mt-1">
          Entity timelines, telemetry, and trend analysis
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Entities"
          value={entities.data?.count ?? 0}
          color="text-gray-800"
        />
        <StatCard
          label="Entity Types"
          value={typeCount}
          color="text-brand-600"
        />
        <StatCard
          label="Avg Confidence"
          value={`${(avgConfidence * 100).toFixed(0)}%`}
          color="text-green-600"
        />
        <StatCard
          label="Source Systems"
          value={sourceSystems.length}
          sub={sourceSystems.join(", ")}
          color="text-blue-600"
        />
      </div>

      {/* Entity Type Breakdown */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Entity Types
        </h2>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setEntityTypeFilter("")}
            className={`text-xs px-3 py-1.5 rounded-full border transition ${
              !entityTypeFilter
                ? "bg-brand-50 border-brand-200 text-brand-700"
                : "border-gray-200 text-gray-500 hover:bg-gray-50"
            }`}
          >
            All ({entities.data?.count ?? 0})
          </button>
          {entityTypes.map((type) => {
            const count = entityList.filter((e) => e._type === type).length;
            return (
              <button
                key={type}
                onClick={() => setEntityTypeFilter(type)}
                className={`text-xs px-3 py-1.5 rounded-full border transition ${
                  entityTypeFilter === type
                    ? "bg-brand-50 border-brand-200 text-brand-700"
                    : "border-gray-200 text-gray-500 hover:bg-gray-50"
                }`}
              >
                {type} ({count})
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Entity Selector */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
            Select Entity for Telemetry
          </h2>
          <select
            value={selectedEntity}
            onChange={(e) => {
              setSelectedEntity(e.target.value);
              setSelectedParam("");
            }}
            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
          >
            <option value="">Choose an entity...</option>
            {entityList.map((e) => (
              <option key={e.id} value={e.id}>
                {(e.name as string) || e.id.slice(0, 12)} ({e._type})
              </option>
            ))}
          </select>

          {/* Parameter selector */}
          {selectedEntity && params.data?.parameters && (
            <div className="mt-3 space-y-2">
              <p className="text-xs font-medium text-gray-500">Parameters</p>
              {params.data.parameters.length === 0 ? (
                <p className="text-xs text-gray-400">
                  No telemetry data for this entity
                </p>
              ) : (
                params.data.parameters.map((p) => (
                  <button
                    key={p.parameter}
                    onClick={() => setSelectedParam(p.parameter)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
                      selectedParam === p.parameter
                        ? "bg-brand-50 text-brand-700"
                        : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-medium">{p.parameter}</span>
                      <span className="text-xs text-gray-400">{p.unit}</span>
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {p.total_readings} readings
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Telemetry chart (table-based) */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
            Telemetry Data
            {selectedParam && (
              <span className="text-brand-600 ml-1 normal-case">
                — {selectedParam}
              </span>
            )}
          </h2>
          {telemetry.data?.data?.length ? (
            <>
              {/* Mini bar chart */}
              <div className="flex items-end gap-0.5 h-24 mb-4">
                {telemetry.data.data.map((pt, i) => {
                  const values = telemetry.data!.data.map((d) => d.avg_value);
                  const max = Math.max(...values);
                  const min = Math.min(...values);
                  const range = max - min || 1;
                  const height =
                    ((pt.avg_value - min) / range) * 80 + 20;
                  return (
                    <div
                      key={i}
                      className="flex-1 bg-brand-400 rounded-t hover:bg-brand-500 transition group relative"
                      style={{ height: `${height}%` }}
                      title={`${pt.avg_value.toFixed(2)} at ${new Date(pt.bucket).toLocaleTimeString()}`}
                    />
                  );
                })}
              </div>
              <div className="overflow-x-auto max-h-48">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100 text-left text-gray-400 uppercase">
                      <th className="pb-1 pr-3">Time</th>
                      <th className="pb-1 pr-3 text-right">Avg</th>
                      <th className="pb-1 pr-3 text-right">Min</th>
                      <th className="pb-1 pr-3 text-right">Max</th>
                      <th className="pb-1 text-right">Samples</th>
                    </tr>
                  </thead>
                  <tbody>
                    {telemetry.data.data.slice(-12).map((pt, i) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-1 pr-3 text-gray-500">
                          {new Date(pt.bucket).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td className="py-1 pr-3 text-right font-medium text-gray-700">
                          {pt.avg_value.toFixed(2)}
                        </td>
                        <td className="py-1 pr-3 text-right text-gray-500">
                          {pt.min_value.toFixed(2)}
                        </td>
                        <td className="py-1 pr-3 text-right text-gray-500">
                          {pt.max_value.toFixed(2)}
                        </td>
                        <td className="py-1 text-right text-gray-400">
                          {pt.sample_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-400">
              {selectedParam ? "No data available" : "Select a parameter to view data"}
            </p>
          )}
        </div>
      </div>

      {/* Trend Analysis */}
      {trend.data?.data?.length ? (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
            Trend Analysis — {selectedParam}
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase">
                  <th className="pb-2 pr-4">Time</th>
                  <th className="pb-2 pr-4 text-right">Value</th>
                  <th className="pb-2 pr-4 text-right">Moving Avg</th>
                  <th className="pb-2 pr-4 text-right">Delta</th>
                  <th className="pb-2 text-right">% Change</th>
                </tr>
              </thead>
              <tbody>
                {trend.data.data.slice(-20).map((pt, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-1.5 pr-4 text-gray-500">
                      {new Date(pt.bucket).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="py-1.5 pr-4 text-right font-medium text-gray-700">
                      {pt.avg_value.toFixed(2)}
                    </td>
                    <td className="py-1.5 pr-4 text-right text-gray-500">
                      {pt.moving_avg_3?.toFixed(2) ?? "—"}
                    </td>
                    <td className="py-1.5 pr-4 text-right">
                      {pt.delta != null ? (
                        <span
                          className={
                            pt.delta > 0
                              ? "text-green-600"
                              : pt.delta < 0
                                ? "text-red-500"
                                : "text-gray-400"
                          }
                        >
                          {pt.delta > 0 ? "+" : ""}
                          {pt.delta.toFixed(2)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-1.5 text-right">
                      {pt.pct_change != null ? (
                        <span
                          className={
                            pt.pct_change > 0
                              ? "text-green-600"
                              : pt.pct_change < 0
                                ? "text-red-500"
                                : "text-gray-400"
                          }
                        >
                          {pt.pct_change > 0 ? "+" : ""}
                          {pt.pct_change.toFixed(1)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Entity Table */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Recent Entities
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase text-gray-400">
                <th className="pb-2 pr-4">Name/ID</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">Source</th>
                <th className="pb-2 pr-4 text-right">Confidence</th>
                <th className="pb-2 pr-4">Version</th>
                <th className="pb-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {entityList.slice(0, 20).map((e) => (
                <tr
                  key={e.id}
                  className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedEntity(e.id)}
                >
                  <td className="py-2 pr-4 font-medium text-gray-700">
                    {(e.name as string) || e.id.slice(0, 12)}
                  </td>
                  <td className="py-2 pr-4">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                      {e._type}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-gray-500">{e._source_system}</td>
                  <td className="py-2 pr-4 text-right">
                    <span
                      className={
                        e._confidence >= 0.9
                          ? "text-green-600"
                          : e._confidence >= 0.7
                            ? "text-yellow-600"
                            : "text-red-500"
                      }
                    >
                      {(e._confidence * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-gray-400">v{e._version}</td>
                  <td className="py-2 text-gray-400 text-xs">
                    {new Date(e._updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
        {label}
      </p>
      <p className={`mt-1 text-3xl font-bold ${color}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}
