import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

const API = "/api/v1";

interface Trainee {
  id: string;
  trainee_code: string;
  name: string;
  email: string | null;
  education_level: string | null;
  field_of_study: string | null;
  years_experience: number;
  career_goals: string[];
  preferred_sectors: string[];
  programme_type: string | null;
  status: string;
  created_at: string;
}

interface TraineeResponse {
  total: number;
  trainees: Trainee[];
}

const STATUS_BADGE: Record<string, string> = {
  applied: "bg-gray-100 text-gray-600",
  enrolled: "bg-blue-100 text-blue-700",
  training: "bg-indigo-100 text-indigo-700",
  completed: "bg-emerald-100 text-emerald-700",
  placed: "bg-green-100 text-green-800",
};

export default function TraineeList() {
  const [status, setStatus] = useState<string>("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading } = useQuery<TraineeResponse>({
    queryKey: ["trainees", status, page],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      params.set("limit", String(limit));
      params.set("offset", String(page * limit));
      return fetch(`${API}/trainees?${params}`).then((r) => r.json());
    },
  });

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Trainees</h1>
          <p className="text-sm text-gray-400 mt-1">
            {data ? `${data.total} trainees` : "Loading..."}
          </p>
        </div>

        {/* Status filter */}
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(0);
          }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        >
          <option value="">All statuses</option>
          <option value="applied">Applied</option>
          <option value="enrolled">Enrolled</option>
          <option value="training">Training</option>
          <option value="completed">Completed</option>
          <option value="placed">Placed</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase text-gray-400">
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Education</th>
              <th className="px-4 py-3">Experience</th>
              <th className="px-4 py-3">Programme</th>
              <th className="px-4 py-3">Sectors</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : data?.trainees.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No trainees found.
                </td>
              </tr>
            ) : (
              data?.trainees.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-gray-50 hover:bg-gray-50/50 transition"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {t.trainee_code}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-800">{t.name}</div>
                    {t.email && (
                      <div className="text-xs text-gray-400">{t.email}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {t.education_level ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-600 tabular-nums">
                    {t.years_experience}y
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {t.programme_type ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {t.preferred_sectors?.map((s) => (
                      <span
                        key={s}
                        className="inline-block mr-1 mb-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                      >
                        {s}
                      </span>
                    ))}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                        STATUS_BADGE[t.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-gray-400">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
