import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

interface Scores {
  relevance?: number;
  accuracy?: number;
  completeness?: number;
  conciseness?: number;
  safety?: number;
}

interface Evaluation {
  id: string;
  thread_id: string;
  query: string;
  response: string;
  scores: Scores;
  overall_score: number;
  issues: string[];
  suggestions: string[];
  evaluated_at: string;
}

interface Metrics {
  total_evaluations: number;
  average_score: number;
  dimensions: Record<string, number | null>;
  distribution: Record<string, number>;
  trend: { day: string; avg_score: number; count: number }[];
}

interface Proposal {
  id: string;
  proposal_type: string;
  title: string;
  description: string;
  changes: unknown[];
  expected_impact: string;
  status: string;
  created_at: string;
}

interface EvalForm {
  query: string;
  response: string;
  context_snippet: string;
}

const EMPTY_FORM: EvalForm = { query: "", response: "", context_snippet: "" };

function scoreBadge(score: number) {
  let color = "bg-red-100 text-red-700";
  if (score >= 4.5) color = "bg-green-100 text-green-700";
  else if (score >= 3.5) color = "bg-blue-100 text-blue-700";
  else if (score >= 2.5) color = "bg-yellow-100 text-yellow-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-bold ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    approved: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    applied: "bg-brand-100 text-brand-700",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? colors.pending}`}>
      {status}
    </span>
  );
}

function ScoreBar({ label, value }: { label: string; value: number | null | undefined }) {
  const v = value ?? 0;
  const pct = (v / 5) * 100;
  let barColor = "bg-red-400";
  if (v >= 4) barColor = "bg-green-500";
  else if (v >= 3) barColor = "bg-blue-500";
  else if (v >= 2) barColor = "bg-yellow-500";
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-xs font-medium text-gray-600 capitalize">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-gray-100">
        <div className={`h-2 rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-xs text-gray-500 text-right">{v > 0 ? v.toFixed(1) : "-"}</span>
    </div>
  );
}

export default function QualityStudio() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"overview" | "evaluate" | "proposals">("overview");
  const [form, setForm] = useState<EvalForm>({ ...EMPTY_FORM });

  const { data: metrics } = useQuery<Metrics>({
    queryKey: ["quality-metrics"],
    queryFn: () => fetch(`${API}/quality/metrics`).then((r) => r.json()),
    refetchInterval: 15_000,
  });

  const { data: evalsData } = useQuery<{ evaluations: Evaluation[] }>({
    queryKey: ["quality-evaluations"],
    queryFn: () => fetch(`${API}/quality/evaluations?limit=30`).then((r) => r.json()),
  });

  const { data: proposalsData } = useQuery<{ proposals: Proposal[] }>({
    queryKey: ["quality-proposals"],
    queryFn: () => fetch(`${API}/quality/proposals`).then((r) => r.json()),
  });

  const evaluateMut = useMutation({
    mutationFn: (body: EvalForm) =>
      fetch(`${API}/quality/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then((r) => {
        if (!r.ok) throw new Error("Evaluation failed");
        return r.json();
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quality-evaluations"] });
      qc.invalidateQueries({ queryKey: ["quality-metrics"] });
      setForm({ ...EMPTY_FORM });
    },
  });

  const generateMut = useMutation({
    mutationFn: () =>
      fetch(`${API}/quality/proposals/generate`, { method: "POST" }).then((r) => {
        if (!r.ok) throw new Error("Generation failed");
        return r.json();
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quality-proposals"] }),
  });

  const patchMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      fetch(`${API}/quality/proposals/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quality-proposals"] }),
  });

  const evaluations = evalsData?.evaluations ?? [];
  const proposals = proposalsData?.proposals ?? [];
  const dims = metrics?.dimensions ?? {};

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Quality Studio</h1>
        <p className="text-sm text-gray-500 mt-1">
          Evaluate agent responses, track quality metrics, and generate improvement proposals
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {(["overview", "evaluate", "proposals"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition capitalize ${
              tab === t
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Evaluations</div>
              <div className="mt-1 text-2xl font-bold text-gray-900">{metrics?.total_evaluations ?? 0}</div>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Avg Score</div>
              <div className="mt-1 text-2xl font-bold text-gray-900">
                {metrics?.average_score ? metrics.average_score.toFixed(1) : "-"}/5
              </div>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Excellent</div>
              <div className="mt-1 text-2xl font-bold text-green-600">{metrics?.distribution?.excellent ?? 0}</div>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Needs Work</div>
              <div className="mt-1 text-2xl font-bold text-red-600">
                {(metrics?.distribution?.poor ?? 0) + (metrics?.distribution?.fair ?? 0)}
              </div>
            </div>
          </div>

          {/* Dimension scores */}
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Quality Dimensions</h2>
            <div className="space-y-3">
              {(["relevance", "accuracy", "completeness", "conciseness", "safety"] as const).map((d) => (
                <ScoreBar key={d} label={d} value={dims[`avg_${d}`]} />
              ))}
            </div>
          </div>

          {/* Trend */}
          {(metrics?.trend?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-gray-200 bg-white p-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">7-Day Trend</h2>
              <div className="flex items-end gap-2 h-24">
                {metrics!.trend.map((t) => {
                  const pct = (t.avg_score / 5) * 100;
                  return (
                    <div key={t.day} className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-[10px] text-gray-500">{t.avg_score.toFixed(1)}</span>
                      <div className="w-full bg-gray-100 rounded-t" style={{ height: "80px" }}>
                        <div
                          className="w-full bg-brand-400 rounded-t transition-all"
                          style={{ height: `${pct}%`, marginTop: `${100 - pct}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-400">{t.day.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recent evaluations */}
          <div className="rounded-xl border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-sm font-semibold text-gray-900">Recent Evaluations</h2>
            </div>
            <div className="divide-y divide-gray-50">
              {evaluations.slice(0, 10).map((ev) => (
                <div key={ev.id} className="px-6 py-3 flex items-center gap-4">
                  {scoreBadge(ev.overall_score)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900 truncate">{ev.query}</p>
                    <p className="text-xs text-gray-400 truncate">{ev.response.slice(0, 120)}...</p>
                  </div>
                  <div className="text-xs text-gray-400 shrink-0">
                    {new Date(ev.evaluated_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
              {evaluations.length === 0 && (
                <div className="px-6 py-8 text-center text-sm text-gray-400">
                  No evaluations yet. Use the Evaluate tab to score agent responses.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Evaluate tab */}
      {tab === "evaluate" && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Evaluate a Response</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Query</label>
            <textarea
              rows={2}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              value={form.query}
              onChange={(e) => setForm((f) => ({ ...f, query: e.target.value }))}
              placeholder="The user's question..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Agent Response</label>
            <textarea
              rows={4}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              value={form.response}
              onChange={(e) => setForm((f) => ({ ...f, response: e.target.value }))}
              placeholder="The agent's response to evaluate..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Context (optional)</label>
            <textarea
              rows={3}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              value={form.context_snippet}
              onChange={(e) => setForm((f) => ({ ...f, context_snippet: e.target.value }))}
              placeholder="Context that was available to the agent..."
            />
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => evaluateMut.mutate(form)}
              disabled={!form.query || !form.response || evaluateMut.isPending}
              className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
            >
              {evaluateMut.isPending ? "Evaluating..." : "Run Evaluation"}
            </button>
            {evaluateMut.isSuccess && evaluateMut.data && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">Score:</span>
                {scoreBadge(evaluateMut.data.overall)}
                {evaluateMut.data.issues?.length > 0 && (
                  <span className="text-xs text-red-500">
                    {evaluateMut.data.issues.length} issue(s)
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Result detail */}
          {evaluateMut.isSuccess && evaluateMut.data && (
            <div className="mt-4 rounded-lg bg-gray-50 border border-gray-200 p-4 space-y-3">
              <h3 className="text-sm font-semibold text-gray-800">Evaluation Result</h3>
              <div className="space-y-2">
                {Object.entries(evaluateMut.data.scores as Scores).map(([k, v]) => (
                  <ScoreBar key={k} label={k} value={v as number} />
                ))}
              </div>
              {evaluateMut.data.issues?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-red-600 mb-1">Issues</h4>
                  <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                    {evaluateMut.data.issues.map((issue: string, i: number) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              {evaluateMut.data.suggestions?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-blue-600 mb-1">Suggestions</h4>
                  <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                    {evaluateMut.data.suggestions.map((s: string, i: number) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Proposals tab */}
      {tab === "proposals" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Improvement Proposals</h2>
            <button
              onClick={() => generateMut.mutate()}
              disabled={generateMut.isPending}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
            >
              {generateMut.isPending ? "Generating..." : "Generate Proposal"}
            </button>
          </div>

          <div className="space-y-3">
            {proposals.map((p) => (
              <div key={p.id} className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{p.title}</h3>
                      {statusBadge(p.status)}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {p.proposal_type} &middot; {new Date(p.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  {p.status === "pending" && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => patchMut.mutate({ id: p.id, status: "approved" })}
                        className="rounded border border-green-200 px-3 py-1 text-xs text-green-700 hover:bg-green-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => patchMut.mutate({ id: p.id, status: "rejected" })}
                        className="rounded border border-red-200 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
                {p.description && (
                  <p className="mt-2 text-sm text-gray-600">{p.description}</p>
                )}
                {p.expected_impact && (
                  <p className="mt-1 text-xs text-brand-600">Expected impact: {p.expected_impact}</p>
                )}
                {(p.changes as unknown[]).length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                      {(p.changes as unknown[]).length} change(s)
                    </summary>
                    <pre className="mt-1 rounded bg-gray-50 p-2 text-[11px] text-gray-600 overflow-auto max-h-40">
                      {JSON.stringify(p.changes, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))}
            {proposals.length === 0 && (
              <div className="text-center py-12 text-gray-400 text-sm">
                No proposals yet. Run evaluations first, then generate improvement proposals.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
