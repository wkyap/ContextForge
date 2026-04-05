# ContextForge Engine

**AI-native, sector-agnostic context engineering platform for AI agents.**

ContextForge is a Compound AI System that combines temporal knowledge graphs, multi-agent orchestration, MCP tools, and dynamic context engineering into a production-ready platform. Build the engine once, swap the domain layer per sector (healthcare, industrial, pharma, finance).

## Architecture

8-layer stack:

| Layer | Component | Technology |
|-------|-----------|------------|
| 7 | Human Governance | Approval queue, graduated autonomy L0-L4 |
| 6 | Self-Evolution | Schema discovery, tool forge, strategy optimizer |
| 5 | Guardrails & Safety | Presidio PII, hallucination check, domain rules |
| 4 | Agent Orchestration | LangGraph multi-agent (orchestrator + specialists) |
| 3 | Context Engine | 6-stage assembly, retrieval fusion router |
| 2 | Skills & MCP Tools | SKILL.md registry, MCP servers |
| 1 | Knowledge Foundation | Neo4j temporal KG, TimescaleDB, Qdrant, PostgreSQL |
| 0 | Data Ingestion | Structured, streaming, documents, APIs |

**Cross-cutting:** LiteLLM gateway, Langfuse observability, Keycloak auth

## Quickstart

### Prerequisites

- Docker Desktop with 16GB+ RAM allocated
- At least one LLM API key (Anthropic or OpenAI)

### Setup

```bash
# 1. Clone and configure
cd contextforge
cp .env.example .env
# Edit .env — set your API keys and change default passwords

# 2. Start core services
docker compose up -d

# 3. Start with observability (Langfuse + ClickHouse)
docker compose --profile observability up -d

# 4. Start everything (including Ollama, Keycloak)
docker compose --profile full up -d
```

### Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | FastAPI backend |
| Frontend | http://localhost:3000 | React dashboard |
| Neo4j Browser | http://localhost:7474 | Knowledge graph explorer |
| Langfuse | http://localhost:3001 | Observability dashboard |
| LiteLLM | http://localhost:4000 | LLM gateway admin |
| Keycloak | http://localhost:8180 | Auth admin console |
| Qdrant | http://localhost:6333 | Vector DB dashboard |

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

## Project Structure

```
contextforge/
├── engine/              # Python backend (FastAPI + LangGraph)
├── frontend/            # React dashboard
├── channels/            # Node.js messaging gateway
├── approval-dashboard/  # Human governance UI
├── domains/             # Domain SKILL.md files
│   ├── healthcare/
│   ├── industrial/
│   ├── pharma/
│   └── finance/
├── data/                # Test and seed data
├── docs/                # Documentation
├── docker-compose.yml   # All-in-one deployment
└── litellm_config.yaml  # LLM routing configuration
```

## Key Concepts

- **SKILL.md** — Every capability is a markdown file with YAML frontmatter. Human-readable, LLM-readable, git-versionable.
- **Temporal KG** — Knowledge graph where every fact has valid_from/valid_to timestamps. Tracks how data changes over time.
- **Context Engineering** — Dynamic, multi-step context management throughout an agent's reasoning loop (not one-shot CAG).
- **MCP Tools** — All tools follow the Model Context Protocol standard (JSON-RPC 2.0).
- **Domain Adapter** — A directory of SKILL.md files that configures the engine for a specific sector.

## Documentation

- [Architecture Guide](docs/architecture.md)
- [Skill Development Guide](docs/skill-development-guide.md)
- [API Reference](docs/api-reference.md)
- [Deployment Guide](docs/deployment-guide.md)

## License

Open Source — see LICENSE for details.
