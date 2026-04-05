# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is ContextForge

AI-native, sector-agnostic context engineering platform. The engine is domain-independent; sector-specific knowledge lives in swappable Domain Adapters composed of SKILL.md files (markdown with YAML frontmatter). Currently includes a CareerForge domain implementation alongside generic sectors (healthcare, industrial, pharma, finance).

## Commands

### Start services
```bash
docker compose up -d                              # Core services only
docker compose --profile observability up -d      # + Langfuse/ClickHouse
docker compose --profile full up -d               # Everything (Ollama, Keycloak, etc.)
```

### Engine (Python backend)
```bash
cd engine
pip install -e ".[dev]"                           # Install with dev deps
uvicorn contextforge.api.main:app --reload        # Run API locally (needs all DBs running)
pytest tests/test_smoke.py -v                     # Smoke tests (require running stack)
pytest tests/ -v                                  # All tests
ruff check .                                      # Lint
ruff format .                                     # Format
mypy .                                            # Type check
```

### Frontend (React dashboard)
```bash
cd frontend && npm install && npm run dev         # Dev server on :3000
cd frontend && npm run build                      # Production build
```

### Approval Dashboard (Governance UI)
```bash
cd approval-dashboard && npm install && npm run dev
```

### Channels (Messaging gateway)
```bash
cd channels && npm install && npm run dev         # tsx watch on gateway.ts
```

### Health check
```bash
curl http://localhost:8000/api/v1/health
```

## Architecture

### 8-Layer Stack
The system is an 8-layer architecture. From bottom to top: Data Ingestion → Skills & MCP Tools → Context Engine → Agent Orchestration → Guardrails → Self-Evolution → Human Governance → Messaging Channels.

### Agent Runtime (engine/contextforge/agents/)
LangGraph multi-agent graph with PostgreSQL-backed checkpointing (`AsyncPostgresSaver`). The graph flows: `budget_check → context_check → orchestrator → specialist(s) → guardrails → END`, with error recovery and human-in-the-loop interrupt gates.

- **graph.py** — Builds and compiles the production LangGraph `StateGraph`
- **orchestrator.py** — Central routing node; produces an `OrchestratorPlan` that selects specialists
- **retrieval_agent.py / analysis_agent.py / action_agent.py** — Specialist PydanticAI agents wrapped as LangGraph nodes
- **state.py** — `AgentState` TypedDict shared across all nodes
- **model_router.py** — 3-tier LLM routing (small/medium/large) through LiteLLM

### Context Engine (engine/contextforge/context/)
6-stage context assembly pipeline: retrieval routing → entity resolution → compression → pruning → composition → caching. The `retrieval_router.py` fuses results from Neo4j (KG), Qdrant (vector), and TimescaleDB (time series).

### Skills System (engine/contextforge/skills/)
SKILL.md files are parsed by `loader.py`, validated by `validator.py`, indexed in `registry.py`, and semantically searchable via `search.py` (Qdrant embeddings). Skills are loaded at startup from the `domains/` directory.

### Knowledge Layer (engine/contextforge/knowledge/)
Temporal knowledge graph (Neo4j) where every fact has `valid_from`/`valid_to`. Includes GraphRAG pipeline, community detection, schema-free entity extraction, and embedding service.

### MCP Servers (engine/contextforge/mcp_servers/)
Tool servers following Model Context Protocol (JSON-RPC 2.0): graph_tools, timeseries_tools, vector_tools, compute_server, sql_server, api_server, document_server.

### Domain Adapter Pattern
Each domain is a directory under `domains/{name}/` with subdirs: schema, ingestion, tools, templates, guardrails, channels — all containing SKILL.md files. New domains require no engine code changes.

## Key Technical Details

- **Python 3.12+**, FastAPI + Pydantic v2, pydantic-settings for config
- **Config**: `engine/contextforge/config.py` — all settings from env vars with `CONTEXTFORGE_` prefix (via `pydantic_settings`)
- **API prefix**: All routes under `/api/v1`
- **DB clients** stored on `app.state` via FastAPI lifespan; injected through `api/deps.py`
- **Ruff** for linting/formatting (line-length 100, target py312, rules: E/F/I/N/W/UP)
- **mypy** strict mode
- **pytest** with `asyncio_mode = "auto"`
- **Observability**: Langfuse tracing via decorators (`@trace_agent`, `@trace_span`, `@trace_tool`)
- **Auth**: Keycloak OIDC — disabled by default in dev (`CONTEXTFORGE_AUTH_DISABLED=true`); see `api/auth.py`
- **LLM calls**: Always routed through LiteLLM gateway, never direct provider SDKs
- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS + Zustand + TanStack Query
