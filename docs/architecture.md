# ContextForge Architecture

> **Canonical architecture reference.** This document is the single source of truth for the ContextForge architecture. Other docs (README, CLAUDE.md, app-level ARCHITECTURE.md files) may summarise but must not redefine the layer model, agent flow, or storage topology.
>
> **Last verified against code:** 2026-04-15.

## Overview

ContextForge is a compound AI system. The **platform** provides a reusable engine; **apps** are domain-specific products built on top. The platform has no hard-coded knowledge of any sector. Sector-specific logic lives in `apps/<name>/` as SKILL.md packs, UI views, and migrations.

See [`platform-vs-domain.md`](platform-vs-domain.md) for how the platform/app split is enforced.

## 8-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  Layer 8: Messaging Channels                │  WhatsApp, Slack, Teams, Web
├─────────────────────────────────────────────┤
│  Layer 7: Human Governance                  │  Approval queue, autonomy levels, audit
├─────────────────────────────────────────────┤
│  Layer 6: Self-Evolution                    │  Schema discovery, tool forge, strategy optimizer
├─────────────────────────────────────────────┤
│  Layer 5: Guardrails                        │  PII, hallucination, provenance, domain safety
├─────────────────────────────────────────────┤
│  Layer 4: Multi-Agent Orchestration         │  LangGraph orchestrator + specialist agents
├─────────────────────────────────────────────┤
│  Layer 3: Context Engine                    │  6-stage assembly, compression, caching
├─────────────────────────────────────────────┤
│  Layer 2: Knowledge Foundation              │  Temporal KG, GraphRAG, vector search, time series
├─────────────────────────────────────────────┤
│  Layer 1: Skills System                     │  SKILL.md parser, registry, semantic search
└─────────────────────────────────────────────┘
```

## Data Stores

| Store | Technology | Purpose |
|-------|-----------|---------|
| App State | PostgreSQL | Skills registry, governance, sessions, audit |
| Knowledge Graph | Neo4j | Temporal entities, relationships, community detection |
| Time Series | TimescaleDB | Entity telemetry, vitals, sensor data |
| Vector Search | Qdrant | Document chunks, entity embeddings, community summaries, skill catalog |
| Cache & Pub/Sub | Redis | Context cache, session state, event bus |
| Observability | Langfuse | LLM traces, cost tracking, prompt versioning |

## Agent Architecture

The agent runtime uses LangGraph with PostgreSQL-backed checkpointing for:
- Multi-turn conversation with full state persistence
- Multi-agent orchestration (orchestrator + specialist agents)
- Budget control (token + cost limits per run)
- Time-travel debugging via checkpoint history

### Agent Flow

```
User Message → Orchestrator Agent
  ├── Context Retrieval (KG + Vector + TimeSeries)
  ├── Tool Selection (MCP servers)
  ├── Specialist Delegation (if needed)
  ├── Guardrail Checks
  └── Response Generation
```

## LLM Gateway

All LLM calls route through LiteLLM, which provides:
- Model-agnostic API (swap providers without code changes)
- 3-tier model routing: small (fast/cheap), medium (balanced), large (complex reasoning)
- Automatic Langfuse callback for cost and latency tracking

## Domain Adapter Pattern

Each domain is a directory of SKILL.md files organized by type:

```
domains/{domain}/
  schema/       → Knowledge skills (entity definitions)
  ingestion/    → Ingestion skills (data source adapters)
  tools/        → Computation skills (domain-specific calculations)
  templates/    → Template skills (output formatting)
  guardrails/   → Guardrail skills (domain safety rules)
  channels/     → Channel skills (messaging configurations)
```

The engine discovers and loads skills at startup. New domains are onboarded by adding a new directory of SKILL.md files — no engine code changes required.

## Authentication & Authorization

- **Identity Provider:** Keycloak (OIDC/OAuth2)
- **Roles:** admin, operator, viewer
- **Dev Mode:** Auth bypass with synthetic admin user
- **API Security:** JWT bearer tokens validated against Keycloak JWKS

## Observability Stack

- **Langfuse:** LLM call tracing, cost tracking, prompt management
- **Trace Decorators:** `@trace_agent`, `@trace_span`, `@trace_tool` for structured tracing
- **Cost Tracker:** Per-run token/cost accumulation with budget enforcement
