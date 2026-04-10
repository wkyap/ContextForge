import { useMemo, useState } from "react";

interface BuilderTask {
  id: string;
  activity: string;
  depends_on: string[];
  retries: number;
}

interface ValidationIssue {
  taskId: string;
  message: string;
}

const STARTER_TASKS: BuilderTask[] = [
  { id: "fetch", activity: "fetch_source", depends_on: [], retries: 0 },
  { id: "parse", activity: "parse_records", depends_on: ["fetch"], retries: 1 },
  { id: "load", activity: "load_to_kg", depends_on: ["parse"], retries: 2 },
];

function validate(tasks: BuilderTask[]): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const ids = new Set<string>();
  for (const t of tasks) {
    if (!t.id) issues.push({ taskId: "", message: "Task is missing an id" });
    if (ids.has(t.id)) issues.push({ taskId: t.id, message: `Duplicate id ${t.id}` });
    ids.add(t.id);
    if (!t.activity) issues.push({ taskId: t.id, message: "Activity name is required" });
    for (const d of t.depends_on) {
      if (d === t.id) {
        issues.push({ taskId: t.id, message: `Cannot depend on itself` });
      }
    }
  }
  for (const t of tasks) {
    for (const d of t.depends_on) {
      if (!ids.has(d)) {
        issues.push({ taskId: t.id, message: `Unknown dependency ${d}` });
      }
    }
  }
  // Cycle detection (DFS).
  const adj = new Map(tasks.map((t) => [t.id, t.depends_on]));
  const color = new Map(tasks.map((t) => [t.id, 0]));
  const visit = (node: string, path: string[]): void => {
    color.set(node, 1);
    for (const dep of adj.get(node) ?? []) {
      if (color.get(dep) === 1) {
        issues.push({
          taskId: node,
          message: `Cycle: ${[...path, node, dep].join(" -> ")}`,
        });
        return;
      }
      if (color.get(dep) === 0) visit(dep, [...path, node]);
    }
    color.set(node, 2);
  };
  for (const t of tasks) if (color.get(t.id) === 0) visit(t.id, []);
  return issues;
}

function topologicalLayers(tasks: BuilderTask[]): string[][] {
  const remaining = new Map(tasks.map((t) => [t.id, new Set(t.depends_on)]));
  const layers: string[][] = [];
  while (remaining.size > 0) {
    const ready: string[] = [];
    for (const [id, deps] of remaining) if (deps.size === 0) ready.push(id);
    if (ready.length === 0) return layers; // cycle
    layers.push(ready);
    for (const id of ready) remaining.delete(id);
    for (const deps of remaining.values()) for (const id of ready) deps.delete(id);
  }
  return layers;
}

function toSkillMd(name: string, description: string, tasks: BuilderTask[]): string {
  const yamlTasks = tasks
    .map(
      (t) =>
        `  - id: ${t.id}\n    activity: ${t.activity}\n    depends_on: [${t.depends_on.join(
          ", ",
        )}]\n    retries: ${t.retries}`,
    )
    .join("\n");
  const slug = name.toLowerCase().replace(/[^a-z0-9_]/g, "_") || "pipeline";
  return `---
name: ${slug}
type: pipeline
domain: _examples
version: "1.0.0"
description: ${description || "Authored in Pipeline Builder"}
author: human
tags: [pipeline, dag]
runner: temporal
task_queue: contextforge-pipelines
tasks:
${yamlTasks}
---

# ${name || slug}

${description || "Pipeline definition emitted by the Pipeline Builder UI."}

## Task graph

\`\`\`
${topologicalLayers(tasks)
  .map((layer, i) => `Layer ${i}: ${layer.join(", ")}`)
  .join("\n")}
\`\`\`
`;
}

export default function PipelineBuilder() {
  const [name, setName] = useState("my_pipeline");
  const [description, setDescription] = useState("");
  const [tasks, setTasks] = useState<BuilderTask[]>(STARTER_TASKS);
  const [copied, setCopied] = useState(false);

  const issues = useMemo(() => validate(tasks), [tasks]);
  const layers = useMemo(
    () => (issues.length === 0 ? topologicalLayers(tasks) : []),
    [issues, tasks],
  );
  const skillMd = useMemo(
    () => toSkillMd(name, description, tasks),
    [name, description, tasks],
  );

  const updateTask = (idx: number, patch: Partial<BuilderTask>) => {
    setTasks((prev) => prev.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  };
  const removeTask = (idx: number) => setTasks((prev) => prev.filter((_, i) => i !== idx));
  const addTask = () =>
    setTasks((prev) => [
      ...prev,
      { id: `task_${prev.length + 1}`, activity: "", depends_on: [], retries: 0 },
    ]);

  const copy = async () => {
    await navigator.clipboard.writeText(skillMd);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pipeline Builder</h1>
        <p className="text-sm text-gray-500 mt-1">
          Compose a DAG of named activities and emit a SKILL.md the Temporal
          worker can execute.
        </p>
      </div>

      <section className="grid grid-cols-2 gap-3 rounded-lg border border-gray-200 bg-white p-5">
        <input
          placeholder="Pipeline name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-800">Tasks</h2>
          <button
            onClick={addTask}
            className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-700"
          >
            + Add task
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="text-left px-2 py-1">ID</th>
                <th className="text-left px-2 py-1">Activity</th>
                <th className="text-left px-2 py-1">Depends on</th>
                <th className="text-left px-2 py-1">Retries</th>
                <th className="text-right px-2 py-1"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tasks.map((t, i) => {
                const taskIssues = issues.filter((iss) => iss.taskId === t.id);
                return (
                  <tr key={i} className={taskIssues.length ? "bg-red-50" : ""}>
                    <td className="px-2 py-1.5">
                      <input
                        value={t.id}
                        onChange={(e) => updateTask(i, { id: e.target.value })}
                        className="w-32 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <input
                        value={t.activity}
                        onChange={(e) => updateTask(i, { activity: e.target.value })}
                        placeholder="activity_name"
                        className="w-44 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <input
                        value={t.depends_on.join(", ")}
                        onChange={(e) =>
                          updateTask(i, {
                            depends_on: e.target.value
                              .split(",")
                              .map((s) => s.trim())
                              .filter(Boolean),
                          })
                        }
                        placeholder="comma,separated"
                        className="w-56 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <input
                        type="number"
                        min={0}
                        value={t.retries}
                        onChange={(e) =>
                          updateTask(i, { retries: parseInt(e.target.value || "0", 10) })
                        }
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-xs"
                      />
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <button
                        onClick={() => removeTask(i)}
                        className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {issues.length > 0 ? (
        <section className="rounded-lg border border-red-200 bg-red-50 p-4">
          <h3 className="text-sm font-semibold text-red-700 mb-2">
            {issues.length} issue(s)
          </h3>
          <ul className="text-xs text-red-700 space-y-1 font-mono">
            {issues.map((iss, i) => (
              <li key={i}>
                {iss.taskId ? `[${iss.taskId}] ` : ""}
                {iss.message}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section className="rounded-lg border border-green-200 bg-green-50 p-4">
          <h3 className="text-sm font-semibold text-green-700 mb-2">
            Topological layers
          </h3>
          <ul className="text-xs text-green-800 font-mono space-y-1">
            {layers.map((layer, i) => (
              <li key={i}>
                <span className="text-green-600">layer {i}:</span> {layer.join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-800">SKILL.md output</h2>
          <button
            onClick={copy}
            className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <pre className="overflow-x-auto rounded bg-gray-900 text-gray-100 text-xs p-4 font-mono">
          {skillMd}
        </pre>
      </section>
    </div>
  );
}
