import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

// ── Domain types ────────────────────────────────────────────────────────────

interface BuilderTask {
  id: string;
  activity: string;
  depends_on: string[];
  retries: number;
}

interface NodePos {
  x: number;
  y: number;
}

interface ValidationIssue {
  taskId: string;
  message: string;
}

// ── Starter data ────────────────────────────────────────────────────────────

const STARTER_TASKS: BuilderTask[] = [
  { id: "fetch", activity: "fetch_source", depends_on: [], retries: 0 },
  { id: "parse", activity: "parse_records", depends_on: ["fetch"], retries: 1 },
  { id: "load", activity: "load_to_kg", depends_on: ["parse"], retries: 2 },
];

// ── Constants ───────────────────────────────────────────────────────────────

const NODE_W = 172;
const NODE_H = 68;
const LAYER_GAP_X = 220;
const NODE_GAP_Y = 100;
const CANVAS_PAD = 60;
const PORT_R = 6;

// ── Validation ──────────────────────────────────────────────────────────────

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

// ── Topology helpers ────────────────────────────────────────────────────────

function topologicalLayers(tasks: BuilderTask[]): string[][] {
  const remaining = new Map(tasks.map((t) => [t.id, new Set(t.depends_on)]));
  const layers: string[][] = [];
  while (remaining.size > 0) {
    const ready: string[] = [];
    for (const [id, deps] of remaining) if (deps.size === 0) ready.push(id);
    if (ready.length === 0) return layers;
    layers.push(ready);
    for (const id of ready) remaining.delete(id);
    for (const deps of remaining.values()) for (const id of ready) deps.delete(id);
  }
  return layers;
}

function autoLayout(tasks: BuilderTask[]): Map<string, NodePos> {
  const layers = topologicalLayers(tasks);
  const positions = new Map<string, NodePos>();
  layers.forEach((layer, li) => {
    const totalH = layer.length * NODE_H + (layer.length - 1) * NODE_GAP_Y;
    const startY = CANVAS_PAD + Math.max(0, (400 - totalH) / 2);
    layer.forEach((id, ni) => {
      positions.set(id, {
        x: CANVAS_PAD + li * LAYER_GAP_X,
        y: startY + ni * (NODE_H + NODE_GAP_Y),
      });
    });
  });
  // Place any un-layered nodes (cycle members) at the right edge.
  const placed = new Set(positions.keys());
  let extra = 0;
  for (const t of tasks) {
    if (!placed.has(t.id)) {
      positions.set(t.id, {
        x: CANVAS_PAD + layers.length * LAYER_GAP_X,
        y: CANVAS_PAD + extra * (NODE_H + NODE_GAP_Y),
      });
      extra++;
    }
  }
  return positions;
}

// ── SKILL.md export ─────────────────────────────────────────────────────────

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

// ── Edge path helper (smooth bezier) ────────────────────────────────────────

function edgePath(from: NodePos, to: NodePos): string {
  const x1 = from.x + NODE_W;
  const y1 = from.y + NODE_H / 2;
  const x2 = to.x;
  const y2 = to.y + NODE_H / 2;
  const dx = Math.abs(x2 - x1) * 0.5;
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

// ── Sub-components ──────────────────────────────────────────────────────────

function GraphNode({
  task,
  pos,
  selected,
  hasError,
  onSelect,
  onDragStart,
  onPortDragStart,
  onPortDrop,
}: {
  task: BuilderTask;
  pos: NodePos;
  selected: boolean;
  hasError: boolean;
  onSelect: () => void;
  onDragStart: (e: React.MouseEvent) => void;
  onPortDragStart: (e: React.MouseEvent) => void;
  onPortDrop: () => void;
}) {
  const borderColor = hasError
    ? "border-red-400"
    : selected
      ? "border-brand-500"
      : "border-gray-300";
  const bg = hasError
    ? "bg-red-50"
    : selected
      ? "bg-brand-50"
      : "bg-white";

  return (
    <g>
      <foreignObject x={pos.x} y={pos.y} width={NODE_W} height={NODE_H}>
        <div
          className={`rounded-lg border-2 ${borderColor} ${bg} shadow-sm h-full flex flex-col justify-center px-3 cursor-grab select-none`}
          onMouseDown={(e) => {
            // Left-click only, not on ports
            if (e.button !== 0) return;
            onSelect();
            onDragStart(e);
          }}
        >
          <div className="text-xs font-semibold text-gray-900 truncate">{task.id}</div>
          <div className="text-[10px] text-gray-500 truncate font-mono">{task.activity || "..."}</div>
          {task.retries > 0 && (
            <div className="text-[9px] text-gray-400 mt-0.5">retries: {task.retries}</div>
          )}
        </div>
      </foreignObject>
      {/* Input port (left center) */}
      <circle
        cx={pos.x}
        cy={pos.y + NODE_H / 2}
        r={PORT_R}
        className="fill-gray-300 stroke-white stroke-2 cursor-crosshair hover:fill-brand-500"
        onMouseUp={(e) => {
          e.stopPropagation();
          onPortDrop();
        }}
      />
      {/* Output port (right center) */}
      <circle
        cx={pos.x + NODE_W}
        cy={pos.y + NODE_H / 2}
        r={PORT_R}
        className="fill-gray-300 stroke-white stroke-2 cursor-crosshair hover:fill-brand-500"
        onMouseDown={(e) => {
          e.stopPropagation();
          e.preventDefault();
          onPortDragStart(e);
        }}
      />
    </g>
  );
}

// ── Detail panel (side) ─────────────────────────────────────────────────────

function DetailPanel({
  task,
  allIds,
  onChange,
  onRemove,
  onClose,
}: {
  task: BuilderTask;
  allIds: string[];
  onChange: (patch: Partial<BuilderTask>) => void;
  onRemove: () => void;
  onClose: () => void;
}) {
  return (
    <div className="w-72 shrink-0 border-l border-gray-200 bg-white p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">Edit task</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none"
        >
          &times;
        </button>
      </div>
      <label className="block">
        <span className="text-xs text-gray-500">ID</span>
        <input
          value={task.id}
          onChange={(e) => onChange({ id: e.target.value })}
          className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm font-mono"
        />
      </label>
      <label className="block">
        <span className="text-xs text-gray-500">Activity</span>
        <input
          value={task.activity}
          onChange={(e) => onChange({ activity: e.target.value })}
          className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm font-mono"
        />
      </label>
      <label className="block">
        <span className="text-xs text-gray-500">Depends on</span>
        <div className="mt-1 space-y-1">
          {allIds
            .filter((id) => id !== task.id)
            .map((id) => (
              <label key={id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={task.depends_on.includes(id)}
                  onChange={(e) => {
                    const next = e.target.checked
                      ? [...task.depends_on, id]
                      : task.depends_on.filter((d) => d !== id);
                    onChange({ depends_on: next });
                  }}
                  className="rounded"
                />
                <span className="font-mono text-xs">{id}</span>
              </label>
            ))}
        </div>
      </label>
      <label className="block">
        <span className="text-xs text-gray-500">Retries</span>
        <input
          type="number"
          min={0}
          value={task.retries}
          onChange={(e) => onChange({ retries: parseInt(e.target.value || "0", 10) })}
          className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
        />
      </label>
      <button
        onClick={onRemove}
        className="w-full rounded border border-red-300 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
      >
        Remove task
      </button>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

type ViewMode = "graph" | "table";

export default function PipelineBuilder() {
  const [name, setName] = useState("my_pipeline");
  const [description, setDescription] = useState("");
  const [tasks, setTasks] = useState<BuilderTask[]>(STARTER_TASKS);
  const [positions, setPositions] = useState<Map<string, NodePos>>(() =>
    autoLayout(STARTER_TASKS),
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("graph");
  const [copied, setCopied] = useState(false);

  // Drag state (node move)
  const dragRef = useRef<{
    taskId: string;
    startMouse: { x: number; y: number };
    startPos: NodePos;
  } | null>(null);

  // Connection-drag state (port → port)
  const connDragRef = useRef<{
    fromId: string;
    startX: number;
    startY: number;
  } | null>(null);
  const [connDragLine, setConnDragLine] = useState<{
    x1: number;
    y1: number;
    x2: number;
    y2: number;
  } | null>(null);

  const svgRef = useRef<SVGSVGElement>(null);

  const issues = useMemo(() => validate(tasks), [tasks]);
  const errorIds = useMemo(
    () => new Set(issues.map((i) => i.taskId)),
    [issues],
  );
  const layers = useMemo(
    () => (issues.length === 0 ? topologicalLayers(tasks) : []),
    [issues, tasks],
  );
  const skillMd = useMemo(
    () => toSkillMd(name, description, tasks),
    [name, description, tasks],
  );

  // Re-layout when tasks change structurally (add/remove).
  const taskIds = tasks.map((t) => t.id).join(",");
  useLayoutEffect(() => {
    setPositions((prev) => {
      const next = autoLayout(tasks);
      // Preserve manually-placed positions for nodes that already exist.
      for (const [id, pos] of prev) {
        if (next.has(id)) next.set(id, pos);
      }
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskIds]);

  const updateTask = useCallback(
    (taskId: string, patch: Partial<BuilderTask>) => {
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, ...patch } : t)),
      );
    },
    [],
  );
  const removeTask = useCallback(
    (taskId: string) => {
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      if (selected === taskId) setSelected(null);
    },
    [selected],
  );
  const addTask = useCallback(() => {
    setTasks((prev) => {
      const newId = `task_${prev.length + 1}`;
      return [
        ...prev,
        { id: newId, activity: "", depends_on: [], retries: 0 },
      ];
    });
  }, []);

  // ── Mouse handlers for node dragging ────────────────────────────────────

  const svgPoint = useCallback(
    (clientX: number, clientY: number) => {
      const svg = svgRef.current;
      if (!svg) return { x: clientX, y: clientY };
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return { x: clientX, y: clientY };
      const svgP = pt.matrixTransform(ctm.inverse());
      return { x: svgP.x, y: svgP.y };
    },
    [],
  );

  const handleNodeDragStart = useCallback(
    (taskId: string, e: React.MouseEvent) => {
      const pos = positions.get(taskId);
      if (!pos) return;
      dragRef.current = {
        taskId,
        startMouse: svgPoint(e.clientX, e.clientY),
        startPos: { ...pos },
      };
    },
    [positions, svgPoint],
  );

  const handlePortDragStart = useCallback(
    (fromId: string, e: React.MouseEvent) => {
      const pos = positions.get(fromId);
      if (!pos) return;
      const sx = pos.x + NODE_W;
      const sy = pos.y + NODE_H / 2;
      connDragRef.current = { fromId, startX: sx, startY: sy };
      const mp = svgPoint(e.clientX, e.clientY);
      setConnDragLine({ x1: sx, y1: sy, x2: mp.x, y2: mp.y });
    },
    [positions, svgPoint],
  );

  const handlePortDrop = useCallback(
    (toId: string) => {
      const conn = connDragRef.current;
      if (!conn || conn.fromId === toId) return;
      // Add dependency: toId now depends on conn.fromId
      setTasks((prev) =>
        prev.map((t) =>
          t.id === toId && !t.depends_on.includes(conn.fromId)
            ? { ...t, depends_on: [...t.depends_on, conn.fromId] }
            : t,
        ),
      );
      connDragRef.current = null;
      setConnDragLine(null);
    },
    [],
  );

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      // Node dragging
      if (dragRef.current) {
        const mp = svgPoint(e.clientX, e.clientY);
        const d = dragRef.current;
        setPositions((prev) => {
          const next = new Map(prev);
          next.set(d.taskId, {
            x: d.startPos.x + (mp.x - d.startMouse.x),
            y: d.startPos.y + (mp.y - d.startMouse.y),
          });
          return next;
        });
      }
      // Connection line dragging
      if (connDragRef.current) {
        const mp = svgPoint(e.clientX, e.clientY);
        setConnDragLine((prev) =>
          prev ? { ...prev, x2: mp.x, y2: mp.y } : null,
        );
      }
    };
    const onMouseUp = () => {
      dragRef.current = null;
      connDragRef.current = null;
      setConnDragLine(null);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [svgPoint]);

  const reLayout = useCallback(() => {
    setPositions(autoLayout(tasks));
  }, [tasks]);

  const copy = async () => {
    await navigator.clipboard.writeText(skillMd);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // ── Canvas size ──────────────────────────────────────────────────────────

  const canvasSize = useMemo(() => {
    let maxX = 800;
    let maxY = 500;
    for (const pos of positions.values()) {
      maxX = Math.max(maxX, pos.x + NODE_W + CANVAS_PAD);
      maxY = Math.max(maxY, pos.y + NODE_H + CANVAS_PAD);
    }
    return { width: maxX, height: maxY };
  }, [positions]);

  // ── Build edges ─────────────────────────────────────────────────────────

  const edges = useMemo(() => {
    const result: { from: string; to: string; key: string }[] = [];
    for (const t of tasks) {
      for (const dep of t.depends_on) {
        if (positions.has(dep) && positions.has(t.id)) {
          result.push({ from: dep, to: t.id, key: `${dep}->${t.id}` });
        }
      }
    }
    return result;
  }, [tasks, positions]);

  const selectedTask = tasks.find((t) => t.id === selected) ?? null;

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 p-6 pb-0 space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pipeline Builder</h1>
          <p className="text-sm text-gray-500 mt-1">
            Compose a DAG of named activities and emit a SKILL.md the Temporal
            worker can execute.
          </p>
        </div>
        <section className="grid grid-cols-2 gap-3 rounded-lg border border-gray-200 bg-white p-4">
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

        {/* Toolbar */}
        <div className="flex items-center gap-3">
          <div className="flex rounded-md border border-gray-200 overflow-hidden text-xs">
            <button
              onClick={() => setViewMode("graph")}
              className={`px-3 py-1.5 font-medium ${viewMode === "graph" ? "bg-brand-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
            >
              Graph
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`px-3 py-1.5 font-medium ${viewMode === "table" ? "bg-brand-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
            >
              Table
            </button>
          </div>
          <button
            onClick={addTask}
            className="rounded bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700"
          >
            + Add task
          </button>
          {viewMode === "graph" && (
            <button
              onClick={reLayout}
              className="rounded border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              Auto-layout
            </button>
          )}
          <div className="flex-1" />
          <span className="text-xs text-gray-400">
            {tasks.length} task{tasks.length !== 1 ? "s" : ""}
            {issues.length > 0 && (
              <span className="text-red-500 ml-2">{issues.length} issue(s)</span>
            )}
          </span>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex min-h-0 p-6 pt-4 gap-4">
        {/* Graph / Table panel */}
        <div className="flex-1 flex flex-col min-w-0">
          {viewMode === "graph" ? (
            <div className="flex-1 rounded-lg border border-gray-200 bg-gray-50 overflow-auto relative">
              <svg
                ref={svgRef}
                width={canvasSize.width}
                height={canvasSize.height}
                className="select-none"
              >
                {/* Grid dots */}
                <defs>
                  <pattern
                    id="grid-dots"
                    width="20"
                    height="20"
                    patternUnits="userSpaceOnUse"
                  >
                    <circle cx="10" cy="10" r="0.8" fill="#d1d5db" />
                  </pattern>
                </defs>
                <rect
                  width={canvasSize.width}
                  height={canvasSize.height}
                  fill="url(#grid-dots)"
                />

                {/* Edges */}
                {edges.map(({ from, to, key }) => {
                  const fp = positions.get(from);
                  const tp = positions.get(to);
                  if (!fp || !tp) return null;
                  return (
                    <path
                      key={key}
                      d={edgePath(fp, tp)}
                      fill="none"
                      stroke="#9ca3af"
                      strokeWidth={2}
                      markerEnd="url(#arrowhead)"
                    />
                  );
                })}

                {/* Arrowhead marker */}
                <defs>
                  <marker
                    id="arrowhead"
                    markerWidth="8"
                    markerHeight="6"
                    refX="7"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 3, 0 6" fill="#9ca3af" />
                  </marker>
                  <marker
                    id="arrowhead-blue"
                    markerWidth="8"
                    markerHeight="6"
                    refX="7"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 3, 0 6" fill="#6366f1" />
                  </marker>
                </defs>

                {/* Connection drag line */}
                {connDragLine && (
                  <line
                    x1={connDragLine.x1}
                    y1={connDragLine.y1}
                    x2={connDragLine.x2}
                    y2={connDragLine.y2}
                    stroke="#6366f1"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    markerEnd="url(#arrowhead-blue)"
                  />
                )}

                {/* Nodes */}
                {tasks.map((task) => {
                  const pos = positions.get(task.id);
                  if (!pos) return null;
                  return (
                    <GraphNode
                      key={task.id}
                      task={task}
                      pos={pos}
                      selected={selected === task.id}
                      hasError={errorIds.has(task.id)}
                      onSelect={() => setSelected(task.id)}
                      onDragStart={(e) => handleNodeDragStart(task.id, e)}
                      onPortDragStart={(e) => handlePortDragStart(task.id, e)}
                      onPortDrop={() => handlePortDrop(task.id)}
                    />
                  );
                })}
              </svg>
              {/* Hint overlay */}
              <div className="absolute bottom-3 left-3 text-[10px] text-gray-400 pointer-events-none">
                Drag nodes to reposition. Drag from right port to left port to connect.
              </div>
            </div>
          ) : (
            /* Table view */
            <div className="flex-1 rounded-lg border border-gray-200 bg-white overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="text-xs uppercase tracking-wide text-gray-500 bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2">ID</th>
                    <th className="text-left px-3 py-2">Activity</th>
                    <th className="text-left px-3 py-2">Depends on</th>
                    <th className="text-left px-3 py-2">Retries</th>
                    <th className="text-right px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tasks.map((t) => {
                    const taskIssues = issues.filter(
                      (iss) => iss.taskId === t.id,
                    );
                    return (
                      <tr
                        key={t.id}
                        className={taskIssues.length ? "bg-red-50" : ""}
                      >
                        <td className="px-3 py-2">
                          <input
                            value={t.id}
                            onChange={(e) =>
                              updateTask(t.id, { id: e.target.value })
                            }
                            className="w-32 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={t.activity}
                            onChange={(e) =>
                              updateTask(t.id, { activity: e.target.value })
                            }
                            placeholder="activity_name"
                            className="w-44 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={t.depends_on.join(", ")}
                            onChange={(e) =>
                              updateTask(t.id, {
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
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            min={0}
                            value={t.retries}
                            onChange={(e) =>
                              updateTask(t.id, {
                                retries: parseInt(
                                  e.target.value || "0",
                                  10,
                                ),
                              })
                            }
                            className="w-16 rounded border border-gray-300 px-2 py-1 text-xs"
                          />
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button
                            onClick={() => removeTask(t.id)}
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
          )}

          {/* Validation / layers strip */}
          {issues.length > 0 ? (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
              <h3 className="text-xs font-semibold text-red-700 mb-1">
                {issues.length} issue(s)
              </h3>
              <ul className="text-[11px] text-red-700 space-y-0.5 font-mono">
                {issues.map((iss, i) => (
                  <li key={i}>
                    {iss.taskId ? `[${iss.taskId}] ` : ""}
                    {iss.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3">
              <h3 className="text-xs font-semibold text-green-700 mb-1">
                Topological layers
              </h3>
              <ul className="text-[11px] text-green-800 font-mono space-y-0.5">
                {layers.map((layer, i) => (
                  <li key={i}>
                    <span className="text-green-600">layer {i}:</span>{" "}
                    {layer.join(", ")}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Detail panel (graph mode) or SKILL.md output */}
        {viewMode === "graph" && selectedTask ? (
          <DetailPanel
            task={selectedTask}
            allIds={tasks.map((t) => t.id)}
            onChange={(patch) => updateTask(selectedTask.id, patch)}
            onRemove={() => removeTask(selectedTask.id)}
            onClose={() => setSelected(null)}
          />
        ) : (
          <div className="w-80 shrink-0 flex flex-col rounded-lg border border-gray-200 bg-white">
            <div className="flex items-center justify-between p-4 pb-2">
              <h2 className="text-sm font-semibold text-gray-800">
                SKILL.md output
              </h2>
              <button
                onClick={copy}
                className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <pre className="flex-1 overflow-auto rounded-b-lg bg-gray-900 text-gray-100 text-[11px] p-4 font-mono m-0">
              {skillMd}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
