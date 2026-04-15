# ContextForge

**A compound-AI context engineering platform. The engine is domain-agnostic; each business use case is an app that plugs in on top.**

ContextForge separates cleanly into two things:

- **Platform** — the reusable engine: temporal knowledge graph, multi-agent orchestration, skills/MCP tools, guardrails, governance, observability, messaging channels.
- **Apps** — domain-specific products built on the platform by packaging SKILL.md files, UI views, and seed data. The reference app is **CareerForge** (workforce / training-to-employment workflows).

The platform boots without any app installed. Apps are enabled at runtime via `CONTEXTFORGE_APPS_ENABLED`.

See [`docs/platform-vs-domain.md`](docs/platform-vs-domain.md) for the split in detail.

---

## Current Status

This repo is in active development. Maturity is uneven by design — the platform surface is broad because it's a proving ground. Trust the maturity matrix below, not the feature list.

| Component | Status | Notes |
|---|---|---|
| Skill registry & loader | Stable | SKILL.md parser, validator, Qdrant-backed search |
| Domain-adapter pattern | Beta | Works; packaging conventions still evolving |
| Agent runtime (LangGraph) | Beta | Graph + checkpointing solid; runtime limits partially hardcoded (see roadmap) |
| Context engine | Beta | 6-stage pipeline; pruning/compression heuristics still maturing |
| Guardrails | Beta | Status model not yet canonicalised (`pass`/`rewrite`/`review`/`block`) |
| Governance (proposals, autonomy, audit) | Beta | Working UI + endpoints; folded into workbench |
| Knowledge layer (Neo4j + GraphRAG) | Beta | Temporal facts work; community detection experimental |
| Connectors & pipelines | Experimental | Scaffolding present; not production-tested |
| Multi-tenancy | Beta | JWT-scoped queries + budgets; row-level security not enforced |
| Messaging channels | Experimental | WhatsApp / Slack gateway; minimal session support |
| Full-stack deployment | Experimental | Works, but 12 services is heavy — prefer the minimal profile |
| CareerForge app | Beta | Only first-class app; used to exercise the platform end-to-end |

Full matrix with rationale: [`docs/component-maturity.md`](docs/component-maturity.md).
What's working today vs. what's planned: [`docs/current-status.md`](docs/current-status.md).

---

## Repository Structure

```
contextforge/
├── platform/
│   ├── engine/              # FastAPI + LangGraph backend (Python)
│   ├── workbench/           # React operator UI (includes /governance/*)
│   └── channels/            # Node.js messaging gateway
├── apps/
│   └── careerforge/         # Reference domain app
│       ├── skills/          # SKILL.md packs (schema, ingestion, tools, templates, guardrails)
│       ├── ui/              # App-specific React views
│       ├── migrations/      # App-owned DB migrations (schema: app_careerforge)
│       └── seed/            # Demo data
├── deploy/
│   ├── compose.minimal.yml  # api + postgres + redis + qdrant + workbench
│   ├── compose.observability.yml
│   ├── compose.full.yml     # everything
│   └── compose.prod.yml
├── docs/
│   ├── architecture.md          # CANONICAL architecture reference
│   ├── platform-vs-domain.md    # How platform and apps are separated
│   ├── component-maturity.md    # What's stable vs. experimental
│   ├── current-status.md        # Implemented / partial / planned
│   ├── security-baseline.md     # Dev defaults, prod expectations
│   ├── deployment-minimal.md    # Fastest evaluation path
│   ├── skill-development-guide.md
│   └── adr/                     # Architecture decision records
└── CLAUDE.md
```

> **Note on the platform/apps split.** The repo is being restructured from a flat `engine/ + frontend/ + domains/` layout into the structure above. If you're looking at an older snapshot, see the restructure branch.

---

## Data Isolation: platform vs app

Data is split by schema/namespace, not by database instance:

| Store | Platform | CareerForge app |
|---|---|---|
| Postgres | schema `platform` | schema `app_careerforge` |
| TimescaleDB | schema `platform` | schema `app_careerforge` |
| Neo4j | label prefix `Platform_*` | label prefix `Cf_*` |
| Qdrant | collections `platform__*` | collections `app_careerforge__*` |
| Redis | keys `cf:platform:*` | keys `cf:app:careerforge:*` |

Apps may read from `platform.*` but write only to their own schema. Platform code never imports from `apps/*`.

---

## Quick Evaluation Path (10 minutes)

Minimum footprint: API + Postgres + Redis + Qdrant + workbench. No Neo4j, no Keycloak, no observability stack.

```bash
cp .env.example .env
# edit .env — set one LLM key (ANTHROPIC_API_KEY or OPENAI_API_KEY)
# change default passwords if exposing beyond localhost

docker compose -f deploy/compose.minimal.yml up -d
curl http://localhost:8000/api/v1/health
# open http://localhost:3000
```

See [`docs/deployment-minimal.md`](docs/deployment-minimal.md) for a walkthrough that exercises one CareerForge workflow end-to-end.

### Full stack (when you need it)

```bash
docker compose -f deploy/compose.full.yml up -d              # everything
docker compose -f deploy/compose.observability.yml up -d     # + Langfuse + ClickHouse
```

### Service URLs (full stack)

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | FastAPI backend |
| Workbench | http://localhost:3000 | Operator UI (platform + enabled apps + governance) |
| Channels gateway | http://localhost:3100 | Messaging webhook receiver |
| Neo4j Browser | http://localhost:7474 | Knowledge graph explorer |
| Langfuse | http://localhost:3001 | LLM traces |
| LiteLLM | http://localhost:4000 | Model gateway admin |
| Keycloak | http://localhost:8180 | Auth admin |
| Qdrant | http://localhost:6333 | Vector DB dashboard |

---

## Security Defaults

Development defaults are deliberately permissive (`CONTEXTFORGE_AUTH_DISABLED=true`, placeholder passwords) so you can try the stack without ceremony. **These are unsafe for anything public.** The engine refuses to boot with placeholder credentials when `CONTEXTFORGE_ENV=prod`.

See [`docs/security-baseline.md`](docs/security-baseline.md) for the hardening checklist.

---

## Building an App

1. Create `apps/<name>/` with `skills/`, `ui/`, `migrations/`, `seed/`.
2. Add SKILL.md files under `skills/` (see [`docs/skill-development-guide.md`](docs/skill-development-guide.md)).
3. Own your schema: migrations write to `app_<name>` in Postgres/Timescale.
4. Register your UI routes via `apps/<name>/ui/routes.ts`.
5. Enable: `CONTEXTFORGE_APPS_ENABLED=<name>`.

The platform needs no code changes to host a new app.

---

## Key Concepts

- **SKILL.md** — Every capability is a markdown file with YAML frontmatter. Human-, LLM-, and git-readable.
- **Temporal KG** — Every fact in the knowledge graph has `valid_from`/`valid_to`; history is first-class.
- **Context Engineering** — Multi-stage context assembly woven through the agent loop, not one-shot retrieval.
- **MCP Tools** — All tools speak Model Context Protocol (JSON-RPC 2.0).
- **Domain Adapter / App** — A directory under `apps/` that configures the platform for a use case without engine changes.

---

## Development

```bash
# Python backend
cd platform/engine
pip install -e ".[dev]"
uvicorn contextforge.api.main:app --reload
pytest -v
ruff check . && ruff format . && mypy .

# Workbench
cd platform/workbench && npm install && npm run dev
```

See [`CLAUDE.md`](CLAUDE.md) for commands and architectural context written for AI assistants working in this repo.

---

## Documentation

- [Architecture (canonical)](docs/architecture.md)
- [Platform vs. domain](docs/platform-vs-domain.md)
- [Component maturity](docs/component-maturity.md)
- [Current status](docs/current-status.md)
- [Security baseline](docs/security-baseline.md)
- [Minimal deployment](docs/deployment-minimal.md)
- [Skill development](docs/skill-development-guide.md)
- [ADRs](docs/adr/)

---

## License

Open Source — see LICENSE for details.
