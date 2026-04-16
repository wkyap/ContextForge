# Current Status

A snapshot of what's implemented, what's partial, and what's planned. Maintained alongside `component-maturity.md` — this file is the narrative view, that one is the table.

**Last updated:** 2026-04-15.

## Implemented (works end-to-end today)

- **Platform/app separation.** Engine under `platform/`, reference app under `apps/careerforge/`. Platform boots without any app installed.
- **Data isolation by schema.** Postgres and Timescale use `platform` and `app_careerforge`; Neo4j label prefixes; Qdrant collection prefixes; Redis key prefixes.
- **Skill registry & loader.** SKILL.md files parsed, validated, indexed in Qdrant, semantically searchable.
- **Agent runtime.** LangGraph graph with Postgres checkpointing. Flow: budget_check → context_check → orchestrator → specialist(s) → guardrails → END. Error recovery + human-in-the-loop interrupts.
- **Context engine.** 6-stage pipeline: retrieval routing → entity resolution → compression → pruning → composition → caching. Fuses Neo4j + Qdrant + Timescale.
- **Knowledge layer.** Temporal KG (valid_from / valid_to), GraphRAG scaffolding, embedding service.
- **Governance.** Proposal queue, autonomy-level promotion, audit log. Workbench `/governance/*` UI (Proposals, Autonomy, Audit).
- **Multi-tenancy (JWT).** Tenant-scoped queries, per-tenant budgets, usage telemetry, connector DLQ.
- **MCP tool servers.** graph, timeseries, vector, compute, sql, api, document.
- **Observability.** Langfuse traces via `@trace_agent`, `@trace_span`, `@trace_tool`.
- **Messaging channels gateway.** WhatsApp / Slack / generic webhook → engine `/agent/chat`.
- **Minimal deployment.** `deploy/compose.minimal.yml`: api + postgres + redis + qdrant + workbench. Boots in under a minute on a laptop.
- **CareerForge app.** Trainees, programmes, courses, employers, job openings, applications, placements, documents, matching results. Dashboard + list views in workbench.

## Partial (usable but rough edges)

- **Guardrail status model.** Works, but producers and the router don't yet agree on one canonical set (`pass` / `rewrite` / `review` / `block`). Drift can cause unexpected routing. Tracked as runtime-hardening.
- **Runtime limits.** Some budget / iteration caps are hardcoded in orchestration. Target: pull from `tenant_budgets` or config. Tracked as runtime-hardening.
- **Template execution.** Naive string substitution. No required-field validation, no escaping. Target: Jinja2 sandbox with typed variables. Tracked as runtime-hardening.
- **Session resume UX.** Backend persists thread history via checkpointing, but the workbench chat view doesn't always render the full prior turn list when resuming.
- **Connectors.** Config CRUD and DLQ exist. Only smoke-tested against mock sources. No scheduled / streaming connectors yet.
- **Quality studio.** CRUD works; eval coverage and regression tracking are thin.
- **Pipeline execution.** Graph editor works; actual pipeline runs execute sequentially with minimal parallelism or retries.
- **Row-level security.** JWT scoping in queries, but Postgres RLS policies not yet applied — defensive depth missing.
- **Prod deployment profile.** No `compose.prod.yml` yet; `.env.example` warnings present but not enforced.

## Planned

- **Hardened runtime contract.** Canonical guardrail statuses; config-driven runtime limits; Jinja-sandboxed templates; deterministic runtime tests (budget-exceeded, retry, fallback, HITL, rewrite loop).
- **`compose.prod.yml`.** No dev server flags, no default secrets, explicit env required, healthchecks + restart policies.
- **Kubernetes manifests.** After the prod compose profile is stable.
- **ADRs.** `0001-platform-vs-domain.md`, `0002-storage-architecture.md`, `0003-skill-registry-design.md`, `0004-agent-runtime-routing.md`.
- **Workbench telemetry panels.** Per-run tokens, cost, latency, model tier, skills & tools used, guardrail outcome. Provenance view for retrieved facts.
- **Second example app.** Only after CareerForge is end-to-end polished. Adding a second app earlier dilutes the proof.
- **Connector catalog.** Real sources (SFTP, S3, HTTP pull, Kafka, CDC) with scheduled ingestion.
- **Benchmarks & failure-mode docs.** Evidence-based, not aspirational.

## Explicitly not on the roadmap

- Broad cross-sector readiness claims. We focus on one domain (CareerForge) until it's excellent.
- Custom UI frameworks. Stay with React + TanStack Query + Zustand + Tailwind.
- Replacing LangGraph, LiteLLM, Langfuse, or Qdrant. They earned their place.
- Direct LLM provider SDK usage. All calls go through LiteLLM.

## Open strategic questions

- Do we bundle a second app now (industrial was the alternative to CareerForge) or prove CareerForge deeper first? Current answer: deeper first.
- Does Neo4j stay mandatory for a minimal deploy, or become opt-in? Current answer: opt-in; minimal profile omits it.
- Should the approval dashboard remain a workbench section or split back out for stricter access boundaries? Current answer: keep folded; revisit if real governance separation is needed.
