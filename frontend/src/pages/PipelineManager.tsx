import { useState, useEffect, useCallback } from "react";

interface Pipeline {
  id: string;
  name: string;
  status: "idle" | "running" | "completed" | "failed";
  documentCount: number;
  lastRunAt: string | null;
  createdAt: string;
}

export default function PipelineManager() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);

  const fetchPipelines = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/pipelines");
      if (res.ok) {
        const data = await res.json();
        setPipelines(data.pipelines || []);
      }
    } catch {
      console.error("Failed to fetch pipelines");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPipelines();
  }, [fetchPipelines]);

  const runPipeline = async (id: string) => {
    try {
      await fetch(`/api/v1/pipelines/${id}/run`, { method: "POST" });
      await fetchPipelines();
    } catch {
      console.error("Failed to run pipeline");
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;
    await uploadFiles(files);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    await uploadFiles(files);
  };

  const uploadFiles = async (files: File[]) => {
    setUploading(true);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      await fetch("/api/v1/pipelines/upload", {
        method: "POST",
        body: formData,
      });
      await fetchPipelines();
    } catch {
      console.error("Failed to upload files");
    } finally {
      setUploading(false);
    }
  };

  const statusColor = (status: Pipeline["status"]) => {
    switch (status) {
      case "running":
        return "bg-blue-100 text-blue-700";
      case "completed":
        return "bg-green-100 text-green-700";
      case "failed":
        return "bg-red-100 text-red-700";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  return (
    <div className="p-6 space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pipeline Manager</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage ingestion pipelines and upload documents for GraphRAG processing.
        </p>
      </div>

      {/* Document Uploader */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          Upload Documents
        </h2>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-10 text-center transition ${
            dragOver
              ? "border-brand-500 bg-brand-50"
              : "border-gray-300 bg-white"
          }`}
        >
          {uploading ? (
            <p className="text-sm text-gray-500 animate-pulse">Uploading...</p>
          ) : (
            <>
              <p className="text-sm text-gray-500">
                Drag and drop files here, or{" "}
                <label className="text-brand-600 cursor-pointer hover:underline">
                  browse
                  <input
                    type="file"
                    multiple
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                </label>
              </p>
              <p className="text-xs text-gray-400 mt-1">
                PDF, DOCX, TXT, MD, JSON supported
              </p>
            </>
          )}
        </div>
      </section>

      {/* Pipeline List */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Pipelines</h2>
        {loading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading...</p>
        ) : pipelines.length === 0 ? (
          <p className="text-sm text-gray-400">
            No pipelines found. Upload documents to create one.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">
                    Documents
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
                  <tr key={p.id}>
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {p.name}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(p.status)}`}
                      >
                        {p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {p.documentCount}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {p.lastRunAt
                        ? new Date(p.lastRunAt).toLocaleString()
                        : "--"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => runPipeline(p.id)}
                        disabled={p.status === "running"}
                        className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                      >
                        Run Pipeline
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
