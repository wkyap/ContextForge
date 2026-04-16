import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API = "/api/v1";

interface Entity {
  id: string;
  _type: string;
  _version: number;
  _is_current: boolean;
  _created_at: string;
  _updated_at: string;
  _confidence: number;
  _source_system: string;
  [key: string]: unknown;
}

interface Relationship {
  type: string;
  rel: Record<string, unknown>;
  target_id: string;
  target_type: string;
}

interface SearchResult {
  entity: Entity;
  score: number;
}

export default function GraphExplorer() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>("");
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Entity list
  const entities = useQuery<{ count: number; entities: Entity[] }>({
    queryKey: ["graph-entities", entityTypeFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "50" });
      if (entityTypeFilter) params.set("entity_type", entityTypeFilter);
      return fetch(`${API}/graph/entities?${params}`).then((r) => r.json());
    },
  });

  // Fulltext search
  const searchResults = useQuery<{ count: number; results: SearchResult[] }>({
    queryKey: ["graph-search", searchQuery],
    queryFn: () =>
      fetch(
        `${API}/graph/search?q=${encodeURIComponent(searchQuery)}&limit=20`
      ).then((r) => r.json()),
    enabled: searchQuery.length > 0,
  });

  // Selected entity details
  const entityDetail = useQuery<Entity>({
    queryKey: ["graph-entity", selectedEntity],
    queryFn: () =>
      fetch(`${API}/graph/entities/${selectedEntity}`).then((r) => r.json()),
    enabled: !!selectedEntity,
  });

  // Relationships
  const relationships = useQuery<{
    count: number;
    relationships: Relationship[];
  }>({
    queryKey: ["graph-rels", selectedEntity],
    queryFn: () =>
      fetch(`${API}/graph/entities/${selectedEntity}/relationships`).then((r) =>
        r.json()
      ),
    enabled: !!selectedEntity,
  });

  // History
  const history = useQuery<{ versions: Entity[] }>({
    queryKey: ["graph-history", selectedEntity],
    queryFn: () =>
      fetch(`${API}/graph/entities/${selectedEntity}/history`).then((r) =>
        r.json()
      ),
    enabled: !!selectedEntity,
  });

  // Create entity
  const createEntity = useMutation({
    mutationFn: (data: {
      entity_type: string;
      properties: Record<string, string>;
    }) =>
      fetch(`${API}/graph/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => r.json()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph-entities"] });
      setShowCreateForm(false);
    },
  });

  const displayEntities = searchQuery
    ? searchResults.data?.results?.map((r) => r.entity) ?? []
    : entities.data?.entities ?? [];

  // Extract unique entity types for filter
  const entityTypes = [
    ...new Set(
      (entities.data?.entities ?? []).map((e) => e._type).filter(Boolean)
    ),
  ];

  const userProps = (entity: Entity) =>
    Object.entries(entity).filter(([k]) => !k.startsWith("_"));

  return (
    <div className="flex h-full">
      {/* Left panel — entity list */}
      <div className="w-96 shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-bold text-gray-800">Graph Explorer</h1>
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="text-xs px-3 py-1.5 bg-brand-600 text-white rounded-md hover:bg-brand-700 transition"
            >
              + Entity
            </button>
          </div>
          <input
            type="text"
            placeholder="Search entities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:ring-1 focus:ring-brand-400 outline-none"
          />
          {entityTypes.length > 0 && (
            <select
              value={entityTypeFilter}
              onChange={(e) => setEntityTypeFilter(e.target.value)}
              className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-600"
            >
              <option value="">All types</option>
              {entityTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Create form */}
        {showCreateForm && <CreateEntityForm onSubmit={createEntity.mutate} />}

        {/* Entity list */}
        <div className="flex-1 overflow-y-auto">
          {displayEntities.length === 0 ? (
            <div className="p-4 text-sm text-gray-400 text-center">
              {entities.isLoading ? "Loading..." : "No entities found"}
            </div>
          ) : (
            displayEntities.map((entity) => (
              <button
                key={`${entity.id}-${entity._version}`}
                onClick={() => setSelectedEntity(entity.id)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition ${
                  selectedEntity === entity.id ? "bg-brand-50" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-800 truncate">
                    {(entity.name as string) || entity.id.slice(0, 12)}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                    {entity._type}
                  </span>
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  v{entity._version} &middot;{" "}
                  {entity._source_system}
                  {entity._confidence < 1 && (
                    <span className="ml-1 text-orange-400">
                      ({(entity._confidence * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right panel — entity detail */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedEntity ? (
          <div className="flex h-full items-center justify-center text-gray-300">
            <div className="text-center">
              <p className="text-lg font-medium">Select an entity</p>
              <p className="text-sm mt-1">
                Choose from the list or search to explore the knowledge graph
              </p>
            </div>
          </div>
        ) : entityDetail.isLoading ? (
          <p className="text-gray-400">Loading...</p>
        ) : entityDetail.data ? (
          <div className="max-w-3xl space-y-6">
            {/* Header */}
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-gray-800">
                  {(entityDetail.data.name as string) ||
                    entityDetail.data.id.slice(0, 12)}
                </h2>
                <span className="text-xs px-2 py-1 rounded-full bg-brand-50 text-brand-700 font-medium">
                  {entityDetail.data._type}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-1 font-mono">
                {entityDetail.data.id}
              </p>
            </div>

            {/* Properties */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                Properties
              </h3>
              <div className="space-y-2">
                {userProps(entityDetail.data).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-start gap-3 text-sm"
                  >
                    <span className="w-32 shrink-0 text-right font-medium text-gray-500">
                      {key}
                    </span>
                    <span className="text-gray-800 break-all">
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Metadata */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                Metadata
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <MetaItem label="Version" value={`v${entityDetail.data._version}`} />
                <MetaItem label="Source" value={entityDetail.data._source_system} />
                <MetaItem label="Confidence" value={`${(entityDetail.data._confidence * 100).toFixed(0)}%`} />
                <MetaItem label="Valid From" value={formatDate(entityDetail.data._valid_from as string)} />
                <MetaItem label="Created" value={formatDate(entityDetail.data._created_at)} />
                <MetaItem label="Updated" value={formatDate(entityDetail.data._updated_at)} />
              </div>
            </div>

            {/* Relationships */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                Relationships ({relationships.data?.count ?? 0})
              </h3>
              {relationships.data?.relationships?.length ? (
                <div className="space-y-2">
                  {relationships.data.relationships.map((rel, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-sm"
                    >
                      <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                        {rel.type}
                      </span>
                      <span className="text-gray-400">&rarr;</span>
                      <button
                        onClick={() => setSelectedEntity(rel.target_id)}
                        className="text-brand-600 hover:underline"
                      >
                        {rel.target_id.slice(0, 12)}
                      </button>
                      <span className="text-[10px] text-gray-400">
                        ({rel.target_type})
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No relationships</p>
              )}
            </div>

            {/* Version History */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                Version History
              </h3>
              {history.data?.versions?.length ? (
                <div className="space-y-2">
                  {history.data.versions.map((v) => (
                    <div
                      key={v._version}
                      className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-700">
                          v{v._version}
                        </span>
                        {v._is_current && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">
                            current
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-400">
                        {v._changed_by as string} &middot;{" "}
                        {formatDate(v._updated_at)}
                        {Boolean(v._change_reason) && (
                          <span className="ml-1 italic">
                            — {v._change_reason as string}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400">Loading...</p>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-400 text-xs">{label}</span>
      <p className="font-medium text-gray-700">{value}</p>
    </div>
  );
}

function CreateEntityForm({
  onSubmit,
}: {
  onSubmit: (data: {
    entity_type: string;
    properties: Record<string, string>;
  }) => void;
}) {
  const [entityType, setEntityType] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <div className="p-4 border-b border-gray-100 bg-gray-50 space-y-2">
      <input
        type="text"
        placeholder="Entity type (e.g. Person)"
        value={entityType}
        onChange={(e) => setEntityType(e.target.value)}
        className="w-full rounded border border-gray-200 px-2.5 py-1.5 text-sm"
      />
      <input
        type="text"
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded border border-gray-200 px-2.5 py-1.5 text-sm"
      />
      <input
        type="text"
        placeholder="Description (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="w-full rounded border border-gray-200 px-2.5 py-1.5 text-sm"
      />
      <button
        onClick={() => {
          if (entityType && name) {
            onSubmit({
              entity_type: entityType,
              properties: { name, description },
            });
          }
        }}
        className="w-full text-sm py-1.5 bg-brand-600 text-white rounded hover:bg-brand-700 transition"
      >
        Create Entity
      </button>
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
