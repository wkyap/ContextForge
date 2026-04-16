import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

type ProposalStatus = "pending" | "approved" | "rejected" | "modified" | "all";

interface Proposal {
  id: string;
  type: string;
  title: string;
  description: string;
  proposed_by: string;
  status: string;
  confidence_score: number;
  created_at: string;
  reviewed_at: string | null;
  approver_id: string | null;
}

interface AutonomyFunction {
  function_name: string;
  autonomy_level: number;
  proposal_count: number;
  approval_count: number;
  approval_rate: number | null;
  promoted_at: string | null;
  promoted_by: string | null;
}

interface AuditEntry {
  id: string;
  timestamp: string;
  user_id: string;
  action_type: string;
  resource_type: string;
  resource_id: string | null;
  result: string;
  reason: string | null;
}

export default function GovernanceDashboard() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ProposalStatus>("pending");
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [reviewerId, setReviewerId] = useState("operator");

  // Proposals
  const proposals = useQuery<{ count: number; proposals: Proposal[] }>({
    queryKey: ["proposals", statusFilter],
    queryFn: () =>
      fetch(`${API}/governance/proposals?status=${statusFilter}&limit=100`).then(
        (r) => r.json(),
      ),
  });

  // Autonomy levels
  const autonomy = useQuery<{
    level_definitions: Record<string, string>;
    functions: AutonomyFunction[];
  }>({
    queryKey: ["autonomy-levels"],
    queryFn: () => fetch(`${API}/governance/autonomy-levels`).then((r) => r.json()),
  });

  // Audit trail (recent)
  const audit = useQuery<{ count: number; entries: AuditEntry[] }>({
    queryKey: ["audit-recent"],
    queryFn: () => fetch(`${API}/governance/audit?limit=25`).then((r) => r.json()),
  });

  // Review mutation
  const review = useMutation({
    mutationFn: (vars: {
      id: string;
      status: "approved" | "rejected" | "modified";
      reason: string;
    }) =>
      fetch(`${API}/governance/proposals/${vars.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: vars.status,
          approver_id: reviewerId,
          reason: vars.reason,
        }),
      }).then((r) => r.json()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["proposals"] });
      queryClient.invalidateQueries({ queryKey: ["audit-recent"] });
      setSelectedProposal(null);
    },
  });

  // Promote mutation
  const promote = useMutation({
    mutationFn: (function_name: string) =>
      fetch(`${API}/governance/autonomy-levels/${function_name}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ promoted_by: reviewerId }),
      }).then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? "Promotion failed");
        return r.json();
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["autonomy-levels"] });
      queryClient.invalidateQueries({ queryKey: ["audit-recent"] });
    },
  });

  const proposalList = proposals.data?.proposals ?? [];
  const pendingCount = proposalList.filter((p) => p.status === "pending").length;
  const functions = autonomy.data?.functions ?? [];
  const avgAutonomy =
    functions.length > 0
      ? functions.reduce((s, f) => s + f.autonomy_level, 0) / functions.length
      : 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Governance Dashboard</h1>
          <p className="text-sm text-gray-400 mt-1">
            Proposal review, autonomy levels, and audit trail
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-gray-500">Reviewer ID:</label>
          <input
            type="text"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
            className="rounded-md border border-gray-200 px-3 py-1.5 text-sm w-32"
          />
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Pending Review"
          value={pendingCount}
          color={pendingCount > 0 ? "text-orange-600" : "text-gray-800"}
        />
        <StatCard
          label="Total Proposals"
          value={proposals.data?.count ?? 0}
          color="text-gray-800"
        />
        <StatCard
          label="Tracked Functions"
          value={functions.length}
          color="text-brand-600"
        />
        <StatCard
          label="Avg Autonomy"
          value={`L${avgAutonomy.toFixed(1)}`}
          sub={autonomy.data?.level_definitions[Math.round(avgAutonomy).toString()] ?? ""}
          color="text-blue-600"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Proposals queue */}
        <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
              Proposals Queue
            </h2>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ProposalStatus)}
              className="text-xs rounded-md border border-gray-200 px-2 py-1 text-gray-600"
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="modified">Modified</option>
              <option value="all">All</option>
            </select>
          </div>

          {proposals.isLoading ? (
            <p className="text-sm text-gray-400">Loading...</p>
          ) : proposalList.length === 0 ? (
            <p className="text-sm text-gray-400">No proposals found</p>
          ) : (
            <div className="space-y-2 max-h-[480px] overflow-y-auto">
              {proposalList.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProposal(p)}
                  className={`w-full text-left rounded-lg border p-3 transition ${
                    selectedProposal?.id === p.id
                      ? "border-brand-300 bg-brand-50"
                      : "border-gray-100 hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-mono">
                          {p.type}
                        </span>
                        <span className="text-sm font-medium text-gray-800 truncate">
                          {p.title}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1 truncate">
                        by {p.proposed_by} · {formatDate(p.created_at)}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <StatusBadge status={p.status} />
                      <ConfidenceBadge score={p.confidence_score} />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected proposal review panel */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
            Review Proposal
          </h2>
          {!selectedProposal ? (
            <p className="text-sm text-gray-400">Select a proposal to review</p>
          ) : (
            <ReviewPanel
              proposal={selectedProposal}
              onSubmit={(status, reason) =>
                review.mutate({ id: selectedProposal.id, status, reason })
              }
              isPending={review.isPending}
            />
          )}
        </div>
      </div>

      {/* Autonomy Levels */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Autonomy Levels
        </h2>

        {/* Level legend */}
        {autonomy.data?.level_definitions && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 mb-4 text-xs">
            {Object.entries(autonomy.data.level_definitions).map(([lvl, desc]) => (
              <div
                key={lvl}
                className="rounded border border-gray-100 bg-gray-50 px-2 py-1.5"
              >
                <span className="font-bold text-brand-600">L{lvl}</span>{" "}
                <span className="text-gray-500">{desc}</span>
              </div>
            ))}
          </div>
        )}

        {functions.length === 0 ? (
          <p className="text-sm text-gray-400">No tracked functions yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase">
                  <th className="pb-2 pr-4">Function</th>
                  <th className="pb-2 pr-4 text-center">Level</th>
                  <th className="pb-2 pr-4 text-right">Proposals</th>
                  <th className="pb-2 pr-4 text-right">Approvals</th>
                  <th className="pb-2 pr-4 text-right">Approval Rate</th>
                  <th className="pb-2 pr-4">Last Promoted</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {functions.map((f) => (
                  <tr key={f.function_name} className="border-b border-gray-50">
                    <td className="py-2 pr-4 font-mono text-xs text-gray-700">
                      {f.function_name}
                    </td>
                    <td className="py-2 pr-4 text-center">
                      <span className="font-bold text-brand-600">L{f.autonomy_level}</span>
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-600">
                      {f.proposal_count}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-600">
                      {f.approval_count}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {f.approval_rate != null ? (
                        <span
                          className={
                            f.approval_rate >= 0.9
                              ? "text-green-600"
                              : f.approval_rate >= 0.7
                                ? "text-yellow-600"
                                : "text-red-500"
                          }
                        >
                          {(f.approval_rate * 100).toFixed(0)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-2 pr-4 text-xs text-gray-400">
                      {f.promoted_at ? formatDate(f.promoted_at) : "—"}
                    </td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => promote.mutate(f.function_name)}
                        disabled={promote.isPending || f.autonomy_level >= 4}
                        className="text-xs px-2 py-1 rounded bg-brand-50 text-brand-700 hover:bg-brand-100 disabled:opacity-40 disabled:cursor-not-allowed"
                        title={
                          f.autonomy_level >= 4
                            ? "Already at max level"
                            : "Promote to next level (requires thresholds met)"
                        }
                      >
                        Promote
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {promote.isError && (
          <p className="mt-3 text-xs text-red-500">
            {(promote.error as Error).message}
          </p>
        )}
      </div>

      {/* Audit Trail */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Recent Audit Trail
        </h2>
        {audit.isLoading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : audit.data?.entries?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase">
                  <th className="pb-2 pr-4">Time</th>
                  <th className="pb-2 pr-4">User</th>
                  <th className="pb-2 pr-4">Action</th>
                  <th className="pb-2 pr-4">Resource</th>
                  <th className="pb-2 pr-4">Result</th>
                  <th className="pb-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.entries.map((e) => (
                  <tr key={e.id} className="border-b border-gray-50">
                    <td className="py-1.5 pr-4 text-xs text-gray-500">
                      {formatDate(e.timestamp)}
                    </td>
                    <td className="py-1.5 pr-4 text-xs text-gray-600">{e.user_id}</td>
                    <td className="py-1.5 pr-4 text-xs font-mono text-gray-700">
                      {e.action_type}
                    </td>
                    <td className="py-1.5 pr-4 text-xs text-gray-500">
                      {e.resource_type}
                      {e.resource_id && (
                        <span className="text-gray-400">
                          {" "}
                          #{e.resource_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 pr-4">
                      <ResultBadge result={e.result} />
                    </td>
                    <td className="py-1.5 text-xs text-gray-400 italic truncate max-w-xs">
                      {e.reason ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">No audit entries yet</p>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

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
      {sub && <p className="mt-1 text-xs text-gray-400 truncate">{sub}</p>}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-orange-50 text-orange-700",
    approved: "bg-green-50 text-green-700",
    rejected: "bg-red-50 text-red-700",
    modified: "bg-blue-50 text-blue-700",
  };
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        styles[status] ?? "bg-gray-50 text-gray-600"
      }`}
    >
      {status}
    </span>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const color =
    score >= 0.9
      ? "text-green-600"
      : score >= 0.7
        ? "text-yellow-600"
        : "text-red-500";
  return (
    <span className={`text-[10px] font-medium ${color}`}>
      {(score * 100).toFixed(0)}% conf
    </span>
  );
}

function ResultBadge({ result }: { result: string }) {
  const styles: Record<string, string> = {
    success: "bg-green-50 text-green-700",
    failure: "bg-red-50 text-red-700",
    escalated_to_human: "bg-orange-50 text-orange-700",
  };
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        styles[result] ?? "bg-gray-50 text-gray-600"
      }`}
    >
      {result}
    </span>
  );
}

function ReviewPanel({
  proposal,
  onSubmit,
  isPending,
}: {
  proposal: Proposal;
  onSubmit: (status: "approved" | "rejected" | "modified", reason: string) => void;
  isPending: boolean;
}) {
  const [reason, setReason] = useState("");
  const isReviewable = proposal.status === "pending";

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs text-gray-400">Title</p>
        <p className="text-sm font-medium text-gray-800">{proposal.title}</p>
      </div>
      <div>
        <p className="text-xs text-gray-400">Type</p>
        <p className="text-sm font-mono text-gray-700">{proposal.type}</p>
      </div>
      <div>
        <p className="text-xs text-gray-400">Description</p>
        <p className="text-sm text-gray-600 whitespace-pre-wrap">
          {proposal.description || "—"}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <p className="text-xs text-gray-400">Confidence</p>
          <p className="text-sm font-medium text-gray-700">
            {(proposal.confidence_score * 100).toFixed(0)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Status</p>
          <StatusBadge status={proposal.status} />
        </div>
      </div>

      {isReviewable ? (
        <>
          <div>
            <label className="text-xs text-gray-400">Reason / Notes</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              className="w-full mt-1 rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:ring-1 focus:ring-brand-400 outline-none"
              placeholder="Why are you approving / rejecting this?"
            />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => onSubmit("approved", reason)}
              disabled={isPending}
              className="text-xs py-2 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => onSubmit("modified", reason)}
              disabled={isPending}
              className="text-xs py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Modify
            </button>
            <button
              onClick={() => onSubmit("rejected", reason)}
              disabled={isPending}
              className="text-xs py-2 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </>
      ) : (
        <p className="text-xs text-gray-400 italic">
          Already reviewed{proposal.approver_id ? ` by ${proposal.approver_id}` : ""}.
        </p>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
