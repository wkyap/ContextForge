# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is ContextForge

A compound-AI **platform** with clean separation from the **apps** that use it:

- **Platform** (`platform/`) — reusable engine: temporal knowledge graph, multi-agent orchestration, skills/MCP tools, context engine, guardrails, governance, observability, messaging channels, operator workbench.
- **Apps** (`apps/`) — domain-specific products packaged as SKILL.md files, UI views, migrations, seed data. The reference app is **CareerForge** (workforce / training → employment).

Canonical architecture: `docs/architecture.md`. Platform/app split rules: `docs/platform-vs-domain.md`.

## Commands

### Start services
```bash
# Minimal (api + postgres + redis + qdrant + workbench):
docker compose -f deploy/compose.minimal.yml up -d
# Full stack:
docker compose -f deploy/compose.full.yml up -d
# Observability (adds Langfuse + ClickHouse):
docker compose -f deploy/compose.observability.yml up -d
```
*(During the restructure, `docker-compose.yml` at the root still works while `deploy/*.yml` files are being introduced.)*

### Engine (Python backend)
```bash
cd platform/engine
pip install -e ".[dev]"                           # Install with dev deps
uvicorn contextforge.api.main:app --reload        # Run API locally (needs DBs running)
pytest tests/test_smoke.py -v                     # Smoke tests
pytest tests/ -v                                  # All tests
ruff check . && ruff format . && mypy .
```

### Workbench (React operator UI — includes governance routes)
```bash
cd platform/workbench && npm install && npm run dev   # :3000
```

### Channels (messaging gateway)
```bash
cd platform/channels && npm install && npm run dev    # tsx watch on gateway.ts
```

### Health check
```bash
curl http://localhost:8000/api/v1/health
```

## Architecture

### 8-Layer stack
Bottom to top: Data Ingestion → Skills & MCP Tools → Context Engine → Agent Orchestration → Guardrails → Self-Evolution → Human Governance → Messaging Channels.

### Agent Runtime (`platform/engine/contextforge/agents/`)
LangGraph multi-agent graph with PostgreSQL-backed checkpointing (`AsyncPostgresSaver`). Flow: `budget_check → context_check → orchestrator → specialist(s) → guardrails → END`, with error recovery and human-in-the-loop interrupt gates.

- **graph.py** — Builds and compiles the production LangGraph `StateGraph`.
- **orchestrator.py** — Central routing node; emits `OrchestratorPlan` selecting specialists.
- **retrieval_agent.py / analysis_agent.py / action_agent.py** — PydanticAI specialists wrapped as LangGraph nodes.
- **state.py** — `AgentState` TypedDict shared across nodes.
- **model_router.py** — 3-tier LLM routing (small/medium/large) through LiteLLM.

### Context Engine (`platform/engine/contextforge/context/`)
6-stage pipeline: retrieval routing → entity resolution → compression → pruning → composition → caching. `retrieval_router.py` fuses Neo4j (KG) + Qdrant (vector) + TimescaleDB (time series).

### Skills System (`platform/engine/contextforge/skills/`)
SKILL.md files parsed by `loader.py`, validated by `validator.py`, indexed in `registry.py`, semantically searched via `search.py` (Qdrant). Skills are loaded at startup from enabled apps: `apps/<name>/skills/` for each entry in `CONTEXTFORGE_APPS_ENABLED`.

### Knowledge Layer (`platform/engine/contextforge/knowledge/`)
Temporal KG (Neo4j) — every fact has `valid_from`/`valid_to`. Includes GraphRAG, community detection, schema-free entity extraction, embedding service.

### MCP Servers (`platform/engine/contextforge/mcp_servers/`)
JSON-RPC 2.0 tool servers: graph_tools, timeseries_tools, vector_tools, compute_server, sql_server, api_server, document_server.

### App Pattern
Each app is a directory under `apps/<name>/` with `skills/` (SKILL.md packs), `ui/` (React views + `routes.ts`), `migrations/` (schema `app_<name>`), `seed/`. No platform code changes are needed to add an app.

## Data Isolation

Platform and apps share DB instances but are separated by schema/namespace:

| Store | Platform | CareerForge app |
|---|---|---|
| Postgres | `platform` schema | `app_careerforge` schema |
| TimescaleDB | `platform` schema | `app_careerforge` schema |
| Neo4j | `Platform_*` labels | `Cf_*` labels |
| Qdrant | `platform__*` collections | `app_careerforge__*` collections |
| Redis | `cf:platform:*` keys | `cf:app:careerforge:*` keys |

Apps may read platform tables but write only to their own schema. Platform code must never import from `apps/*`.

## Key Technical Details

- **Python 3.12+**, FastAPI + Pydantic v2, pydantic-settings for config.
- **Config**: `platform/engine/contextforge/config.py` — all settings from env vars with `CONTEXTFORGE_` prefix.
- **API prefix**: All routes under `/api/v1`.
- **DB clients** stored on `app.state` via FastAPI lifespan; injected through `api/deps.py`.
- **Ruff** for linting/formatting (line-length 100, target py312, rules: E/F/I/N/W/UP).
- **mypy** strict mode.
- **pytest** with `asyncio_mode = "auto"`.
- **Observability**: Langfuse via `@trace_agent`, `@trace_span`, `@trace_tool`.
- **Auth**: Keycloak OIDC — disabled by default in dev (`CONTEXTFORGE_AUTH_DISABLED=true`); see `api/auth.py`.
- **LLM calls**: Always routed through LiteLLM; never direct provider SDKs.
- **Workbench**: React 18 + TypeScript + Vite + TailwindCSS + Zustand + TanStack Query.
