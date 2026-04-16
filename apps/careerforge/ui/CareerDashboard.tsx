import { useQuery } from "@tanstack/react-query";

const API = "/api/v1";

interface KPI {
  total_trainees: number;
  placement_rate: number;
  pending_verifications: number;
  pending_enrolments: number;
}

interface DashboardData {
  kpi: KPI;
  trainee_status: Record<string, number>;
  active_trainees: number;
  completed: number;
  placed: number;
}

interface FunnelData {
  funnel: Record<string, number>;
}

interface AtRiskData {
  at_risk_count: number;
  trainees: Array<{
    id: string;
    trainee_code: string;
    name: string;
    programme_type: string;
    status: string;
    risk_reason: string;
    recommended_action: string;
  }>;
}

function KPICard({
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

function StatusBar({
  label,
  count,
  total,
  color,
}: {
  label: string;
  count: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-right text-xs font-medium text-gray-500 capitalize">
        {label}
      </span>
      <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-12 text-xs font-semibold text-gray-600 tabular-nums">
        {count}
      </span>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  applied: "bg-gray-400",
  enrolled: "bg-blue-400",
  training: "bg-brand-500",
  completed: "bg-emerald-400",
  placed: "bg-green-600",
};

const FUNNEL_LABELS: Record<string, string> = {
  applied: "Applied",
  enrolled: "Enrolled",
  training: "In Training",
  completed: "Completed",
  placed: "Placed",
};

export default function CareerDashboard() {
  const dashboard = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: () => fetch(`${API}/reports/dashboard`).then((r) => r.json()),
  });

  const funnel = useQuery<FunnelData>({
    queryKey: ["funnel"],
    queryFn: () =>
      fetch(`${API}/reports/placement-funnel`).then((r) => r.json()),
  });

  const atRisk = useQuery<AtRiskData>({
    queryKey: ["at-risk"],
    queryFn: () => fetch(`${API}/reports/at-risk`).then((r) => r.json()),
  });

  const d = dashboard.data;
  const f = funnel.data?.funnel;
  const totalFunnel = f
    ? Object.values(f).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">
          CareerForge Dashboard
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          NTUC LearningHub Career Placement Programme
        </p>
      </div>

      {/* KPI Cards */}
      {d && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="Total Trainees"
            value={d.kpi.total_trainees}
            color="text-gray-800"
          />
          <KPICard
            label="Placement Rate"
            value={`${d.kpi.placement_rate}%`}
            sub={`${d.placed} placed / ${d.completed} completed`}
            color="text-green-600"
          />
          <KPICard
            label="Active in Training"
            value={d.active_trainees}
            color="text-brand-600"
          />
          <KPICard
            label="Pending Reviews"
            value={d.kpi.pending_verifications + d.kpi.pending_enrolments}
            sub={`${d.kpi.pending_verifications} docs + ${d.kpi.pending_enrolments} enrolments`}
            color="text-orange-500"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Placement Funnel */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
            Placement Funnel
          </h2>
          {f ? (
            <div className="space-y-3">
              {Object.entries(FUNNEL_LABELS).map(([key, label]) => (
                <StatusBar
                  key={key}
                  label={label}
                  count={f[key] ?? 0}
                  total={totalFunnel}
                  color={STATUS_COLORS[key] ?? "bg-gray-300"}
                />
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Loading...</p>
          )}
        </div>

        {/* Trainee Status Breakdown */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
            Status Breakdown
          </h2>
          {d ? (
            <div className="space-y-2">
              {Object.entries(d.trainee_status).map(([status, count]) => (
                <div
                  key={status}
                  className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        STATUS_COLORS[status] ?? "bg-gray-300"
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-700 capitalize">
                      {status}
                    </span>
                  </div>
                  <span className="text-sm font-bold text-gray-800 tabular-nums">
                    {count}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Loading...</p>
          )}
        </div>
      </div>

      {/* At-Risk Trainees */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
          At-Risk Trainees{" "}
          {atRisk.data && (
            <span className="text-orange-500 ml-1">
              ({atRisk.data.at_risk_count})
            </span>
          )}
        </h2>
        {atRisk.data && atRisk.data.trainees.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase text-gray-400">
                  <th className="pb-2 pr-4">Code</th>
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4">Programme</th>
                  <th className="pb-2 pr-4">Risk Reason</th>
                  <th className="pb-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {atRisk.data.trainees.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-gray-50 hover:bg-orange-50/50"
                  >
                    <td className="py-2 pr-4 font-mono text-xs">
                      {t.trainee_code}
                    </td>
                    <td className="py-2 pr-4">{t.name}</td>
                    <td className="py-2 pr-4 text-gray-500">
                      {t.programme_type}
                    </td>
                    <td className="py-2 pr-4 text-orange-600 text-xs">
                      {t.risk_reason}
                    </td>
                    <td className="py-2 text-xs text-gray-400">
                      {t.recommended_action}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-400 text-sm">
            {atRisk.isLoading
              ? "Loading..."
              : "No at-risk trainees detected."}
          </p>
        )}
      </div>
    </div>
  );
}
