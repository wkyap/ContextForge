# Platform vs. Domain App

ContextForge is **two things**, deliberately kept separate.

## Platform

The reusable engine. Has no knowledge of any specific business problem.

**Lives in:** `platform/`

**Owns:**
- FastAPI backend, LangGraph agent runtime, context engine, skills/MCP tools
- Governance (proposals, autonomy levels, audit)
- Connectors & pipelines
- Messaging channels gateway
- Operator workbench UI (including `/governance/*`)
- Multi-tenancy, budgets, observability
- Postgres schema `platform`, Neo4j labels `Platform_*`, Qdrant collections `platform__*`

**Rules:**
- Platform code must **never import from `apps/*`**. Enforced by import-linter.
- Platform migrations live in `platform/engine/migrations/` and only touch the `platform` schema.
- Platform UI shows platform features only — no hard-coded domain terms in the shell.

## Domain App

A business use case packaged on top of the platform. The reference app is **CareerForge** (workforce training → employment matching). Other apps are hypothetical until they're built.

**Lives in:** `apps/<name>/`

**Owns:**
- Its SKILL.md packs (`skills/`)
- Its domain UI views (`ui/`)
- Its migrations (`migrations/`) — Postgres schema `app_<name>`, Neo4j labels `<Prefix>_*`, Qdrant `app_<name>__*`
- Its seed / demo data (`seed/`)
- Its own `ARCHITECTURE.md`

**Rules:**
- App code imports only from `platform.engine.sdk` (curated surface: DB session, skill registry, guardrails, tracing).
- Apps may read from the `platform` schema. Apps write only to their own schema.
- App UI mounts into the workbench shell via `apps/<name>/ui/routes.ts`.

## Example: CareerForge

```
apps/careerforge/
├── skills/          # e.g. match_trainee_to_job, analyse_resume
├── ui/
│   ├── routes.ts    # declares /careerforge/trainees, /careerforge/dashboard
│   ├── TraineeList.tsx
│   └── CareerDashboard.tsx
├── migrations/
│   └── postgres/    # programmes, trainees, courses, employers, jobs, applications, placements, documents, matching_results
├── seed/
└── ARCHITECTURE.md
```

CareerForge's `app_careerforge.trainees` table may FK to `platform.tenants`. The reverse is never allowed.

## Booting without apps

The platform boots with zero apps installed (`CONTEXTFORGE_APPS_ENABLED=`). This is a useful CI sanity test: if platform code accidentally depends on CareerForge, platform-only boot fails.

Enabling one app:

```
CONTEXTFORGE_APPS_ENABLED=careerforge
```

Enabling multiple apps (once a second exists):

```
CONTEXTFORGE_APPS_ENABLED=careerforge,finance
```

## Why split this way

| Alternative | Why not |
|---|---|
| All one codebase, no separation | The original state. Domain leaked into platform terms and UI, which made the project hard to reposition. |
| Separate database instance per app | Breaks minimal deploy; governance dashboards need to read app data for quality panels; forces Postgres FDW for joins. |
| Separate Postgres DB per app | Same joinability problem; two migration tools; doubles the DSN config. |
| Separate schemas in same DB (current) | Keeps joins cheap, gives per-app `GRANT`s, makes `DROP SCHEMA app_x CASCADE` a clean uninstall. Swap to separate instance later without code changes. |

## Checklist when adding a new app

1. `apps/<name>/` with the 4 subdirs above.
2. First migration creates `app_<name>` schema (see existing `apps/careerforge/migrations/postgres/001_schemas.sql`).
3. Skills register a namespace in their YAML frontmatter.
4. Route manifest declares UI routes, prefixed with the app name.
5. Add `<name>` to `CONTEXTFORGE_APPS_ENABLED` in your local `.env`.
6. Add row to component-maturity matrix.
