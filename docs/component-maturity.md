# Component Maturity

Honest view of what's production-ready, what's prototype, and what's still aspirational.

**Status definitions:**
- **Stable** — works, tested, unlikely to change shape.
- **Beta** — works in the happy path; edge cases and contracts still shifting.
- **Experimental** — present, useful for demo, not battle-tested. Expect breakage.
- **Planned** — not implemented. On the roadmap.

**Last reviewed:** 2026-04-15.

## Platform

| Component | Status | Evidence / Notes |
|---|---|---|
| Skill loader + validator | Stable | `platform/engine/contextforge/skills/`. Covered by smoke tests. |
| Skill semantic search (Qdrant) | Stable | Works end-to-end; indexed at startup. |
| Agent runtime (LangGraph) | Beta | Graph compiles; Postgres checkpointer works. Budget/iteration limits partially hardcoded — see roadmap. |
| Orchestrator routing | Beta | Emits plans; routing logic and guardrail status model not yet canonical (see runtime-hardening backlog). |
| Context engine (6-stage) | Beta | Retrieval router + compression work; pruning heuristics still tuning. |
| Knowledge graph (Neo4j temporal) | Beta | Valid-from / valid-to modelled; community detection is experimental. |
| GraphRAG | Experimental | Community summaries built; retrieval quality not benchmarked. |
| Guardrails | Beta | Works, but status outcomes (`pass`/`rewrite`/`review`/`block`) not yet canonicalised across producers and router. |
| Governance (proposals, autonomy, audit) | Beta | API + UI (now under workbench `/governance/*`). Autonomy promotion works. |
| Multi-tenancy (JWT, budgets) | Beta | JWT-scoped queries, per-tenant budgets, usage log. RLS not enforced in Postgres. |
| Connectors | Experimental | Scaffolding + DLQ. Not exercised against real connector catalog. |
| Pipelines (graph editor) | Experimental | Drag-and-drop builder exists; execution semantics minimal. |
| Quality studio | Experimental | CRUD + eval scaffold. Metric coverage thin. |
| Observability (Langfuse) | Stable | Trace decorators wired through runtime. |
| Auth (Keycloak OIDC) | Beta | Disabled by default in dev. Prod hardening guide in `security-baseline.md`. |
| Messaging channels gateway | Experimental | WhatsApp/Slack webhook shim. Session handling minimal. |
| MCP tool servers | Beta | graph/timeseries/vector/compute/sql/api/document servers implemented. |
| Workbench UI | Beta | Operator views cover most platform surfaces. Loading/error states inconsistent. |

## Apps

| App | Status | Notes |
|---|---|---|
| CareerForge | Beta | First-class reference app. Covers ingestion, matching, placement, dashboards. Still evolving. |
| *(other domains)* | Not present | Former `finance`/`healthcare`/`industrial`/`pharma` placeholders were removed in the restructure. Add a real app when needed. |

## Deployment

| Profile | Status | Notes |
|---|---|---|
| `deploy/compose.minimal.yml` | Beta | api + postgres + redis + qdrant + workbench. Fastest evaluation path. |
| `deploy/compose.observability.yml` | Beta | Adds Langfuse + ClickHouse. |
| `deploy/compose.full.yml` | Experimental | 12 services. Works on a well-resourced machine. |
| `deploy/compose.prod.yml` | Planned | Hardened defaults, no dev flags. Not yet written. |
| Kubernetes manifests | Planned | — |

## What "stable" does **not** mean here

- It does not mean load-tested at scale.
- It does not mean a frozen API contract — minor version bumps may change shapes.
- It means: we don't expect to rewrite this component in the next quarter, and it has enough test coverage that regressions are caught.

## How to update this file

When you change a component's maturity, update the row and bump the "Last reviewed" date. Don't raise status without at least a smoke test covering the happy path; don't leave a component at "Stable" after an API break.
