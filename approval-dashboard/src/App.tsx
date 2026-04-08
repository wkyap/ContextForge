import { useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 10_000 } },
});

const API = "/api/v1";

type Tab = "proposals" | "autonomy" | "audit";

interface Proposal {
  id: string;
  type: string;
  title: string;
  description?: string;
  proposed_by: string;
  status: string;
  confidence_score: number;
  created_at: string;
  reviewed_at?: string | null;
  approver_id?: string | null;
}

interface AutonomyFn {
  function_name: string;
  autonomy_level: number;
  proposal_count: number;
  approval_count: number;
  approval_rate: number;
  promoted_at?: string | null;
  promoted_by?: string | null;
}

interface AuditEntry {
  id: number | string;
  timestamp: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details?: Record<string, unknown>;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-amber-100 text-amber-800 border-amber-200",
    approved: "bg-emerald-100 text-emerald-800 border-emerald-200",
    rejected: "bg-rose-100 text-rose-800 border-rose-200",
    modified: "bg-sky-100 text-sky-800 border-sky-200",
  };
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${
        styles[status] || "bg-gray-100 text-gray-700 border-gray-200"
      }`}
    >
      {status}
    </span>
  );
}

function ProposalsTab() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("pending");
  const [selected, setSelected] = useState<Proposal | null>(null);
  const [reason, setReason] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["proposals", statusFilter],
    queryFn: () =>
      api<{ count: number; proposals: Proposal[] }>(
        `/governance/proposals?status=${statusFilter}&limit=100`,
      ),
  });

  const review = useMutation({
    mutationFn: async (vars: { id: string; status: string }) =>
      api(`/governance/proposals/${vars.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          status: vars.status,
          approver_id: "dashboard-user",
          reason,
        }),
      }),
    onSuccess: () => {
      setSelected(null);
      setReason("");
      qc.invalidateQueries({ queryKey: ["proposals"] });
    },
  });

  return (
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-7">
        <div className="mb-4 flex items-center gap-2">
          {(["pending", "approved", "rejected", "all"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`rounded px-3 py-1 text-sm font-medium transition ${
                statusFilter === s
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-gray-700 hover:bg-gray-100 border border-gray-200"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {isLoading && <div className="text-gray-500">Loading…</div>}
        {error && (
          <div className="rounded bg-rose-50 p-3 text-rose-700">
            {(error as Error).message}
          </div>
        )}

        <div className="space-y-2">
          {data?.proposals.map((p) => (
            <div
              key={p.id}
              onClick={() => setSelected(p)}
              className={`cursor-pointer rounded-lg border bg-white p-4 transition hover:border-indigo-300 hover:shadow-sm ${
                selected?.id === p.id ? "border-indigo-500 shadow-sm" : "border-gray-200"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <StatusPill status={p.status} />
                    <span className="text-xs text-gray-500">{p.type}</span>
                  </div>
                  <div className="mt-1 truncate font-medium text-gray-900">
                    {p.title}
                  </div>
                  <div className="mt-1 truncate text-sm text-gray-500">
                    by {p.proposed_by} ·{" "}
                    {new Date(p.created_at).toLocaleString()}
                  </div>
                </div>
                <div className="text-right text-xs text-gray-400">
                  conf {(p.confidence_score * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          ))}
          {data?.proposals.length === 0 && (
            <div className="rounded border border-dashed border-gray-300 p-8 text-center text-gray-400">
              No {statusFilter} proposals
            </div>
          )}
        </div>
      </div>

      <div className="col-span-5">
        {selected ? (
          <div className="sticky top-6 rounded-lg border border-gray-200 bg-white p-5">
            <StatusPill status={selected.status} />
            <h2 className="mt-2 text-lg font-semibold">{selected.title}</h2>
            <p className="mt-1 text-sm text-gray-600">
              {selected.description || "—"}
            </p>

            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div>
                <dt className="text-gray-400">Type</dt>
                <dd className="font-mono text-gray-700">{selected.type}</dd>
              </div>
              <div>
                <dt className="text-gray-400">Proposed by</dt>
                <dd className="font-mono text-gray-700">{selected.proposed_by}</dd>
              </div>
              <div>
                <dt className="text-gray-400">Confidence</dt>
                <dd className="font-mono text-gray-700">
                  {(selected.confidence_score * 100).toFixed(1)}%
                </dd>
              </div>
              <div>
                <dt className="text-gray-400">Created</dt>
                <dd className="font-mono text-gray-700">
                  {new Date(selected.created_at).toLocaleString()}
                </dd>
              </div>
            </dl>

            {selected.status === "pending" && (
              <div className="mt-5 space-y-3">
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Reason (optional)"
                  rows={3}
                  className="w-full rounded border border-gray-200 p-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() =>
                      review.mutate({ id: selected.id, status: "approved" })
                    }
                    disabled={review.isPending}
                    className="flex-1 rounded bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() =>
                      review.mutate({ id: selected.id, status: "rejected" })
                    }
                    disabled={review.isPending}
                    className="flex-1 rounded bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
                {review.error && (
                  <div className="text-xs text-rose-600">
                    {(review.error as Error).message}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
            Select a proposal to review
          </div>
        )}
      </div>
    </div>
  );
}

function AutonomyTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["autonomy"],
    queryFn: () =>
      api<{
        level_definitions: Record<string, string>;
        functions: AutonomyFn[];
      }>("/governance/autonomy-levels"),
  });

  const promote = useMutation({
    mutationFn: (fn: string) =>
      api(`/governance/autonomy-levels/${fn}/promote`, {
        method: "POST",
        body: JSON.stringify({ promoted_by: "dashboard-user" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["autonomy"] }),
  });

  if (isLoading) return <div className="text-gray-500">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">
          Autonomy levels
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs md:grid-cols-4">
          {Object.entries(data?.level_definitions ?? {}).map(([lvl, desc]) => (
            <div key={lvl}>
              <span className="font-mono text-indigo-600">L{lvl}</span>{" "}
              <span className="text-gray-600">{desc}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-2 text-left">Function</th>
              <th className="px-4 py-2 text-left">Level</th>
              <th className="px-4 py-2 text-right">Proposals</th>
              <th className="px-4 py-2 text-right">Approvals</th>
              <th className="px-4 py-2 text-right">Approval rate</th>
              <th className="px-4 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data?.functions.map((f) => (
              <tr key={f.function_name}>
                <td className="px-4 py-2 font-mono text-gray-800">
                  {f.function_name}
                </td>
                <td className="px-4 py-2">
                  <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                    L{f.autonomy_level}
                  </span>
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {f.proposal_count}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {f.approval_count}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {(f.approval_rate * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => promote.mutate(f.function_name)}
                    disabled={promote.isPending}
                    className="rounded border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                  >
                    Promote
                  </button>
                </td>
              </tr>
            ))}
            {data?.functions.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-gray-400">
                  No autonomy records
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AuditTab() {
  const [actionFilter, setActionFilter] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["audit", actionFilter],
    queryFn: () =>
      api<{ count: number; entries: AuditEntry[] }>(
        `/governance/audit?limit=200${
          actionFilter ? `&action_type=${encodeURIComponent(actionFilter)}` : ""
        }`,
      ),
  });

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <input
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          placeholder="Filter by action type…"
          className="w-64 rounded border border-gray-200 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
        />
        {data && (
          <span className="text-xs text-gray-500">
            {data.count} entries
          </span>
        )}
      </div>

      {isLoading && <div className="text-gray-500">Loading…</div>}

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-2 text-left">When</th>
              <th className="px-4 py-2 text-left">User</th>
              <th className="px-4 py-2 text-left">Action</th>
              <th className="px-4 py-2 text-left">Resource</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data?.entries.map((e) => (
              <tr key={e.id}>
                <td className="px-4 py-2 font-mono text-xs text-gray-500">
                  {new Date(e.timestamp).toLocaleString()}
                </td>
                <td className="px-4 py-2 font-mono text-gray-700">{e.user_id}</td>
                <td className="px-4 py-2">
                  <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                    {e.action}
                  </span>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-gray-600">
                  {e.resource_type}/{e.resource_id}
                </td>
              </tr>
            ))}
            {data?.entries.length === 0 && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-gray-400">
                  No audit entries
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Shell() {
  const [tab, setTab] = useState<Tab>("proposals");
  const tabs: { id: Tab; label: string }[] = [
    { id: "proposals", label: "Proposals" },
    { id: "autonomy", label: "Autonomy" },
    { id: "audit", label: "Audit" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-baseline justify-between">
            <h1 className="text-xl font-semibold text-gray-900">
              ContextForge · Approval Dashboard
            </h1>
            <span className="text-xs text-gray-400">Human governance</span>
          </div>
          <nav className="mt-3 flex gap-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-t border-b-2 px-3 py-1.5 text-sm font-medium transition ${
                  tab === t.id
                    ? "border-indigo-600 text-indigo-700"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-6">
        {tab === "proposals" && <ProposalsTab />}
        {tab === "autonomy" && <AutonomyTab />}
        {tab === "audit" && <AuditTab />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell />
    </QueryClientProvider>
  );
}
