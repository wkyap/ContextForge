# Restructure: Platform / Apps split

Implementation summary for the `restructure/platform-apps-split` branch.
Covers commits `7393961..HEAD` (2026-04-14 → 2026-04-16).

## Goal

Separate the reusable engine (**platform**) from domain-specific products
(**apps**) so a second app can be added without touching platform code, and so
data isolation is enforceable at the store level.

Authoritative reference: [`architecture.md`](architecture.md) +
[`platform-vs-domain.md`](platform-vs-domain.md).

## Before → After

```
Before                                 After
──────                                 ─────
engine/                                platform/engine/
frontend/                              platform/workbench/
channels/                              platform/channels/
approval-dashboard/                    (deleted — already in workbench)
domains/workforce/                     apps/careerforge/skills/
domains/{finance,industrial,pharma}/   (deleted — placeholders)
domains/{healthcare,_examples}/        (deleted — non-app sample content)
frontend/src/pages/CareerDashboard.tsx apps/careerforge/ui/CareerDashboard.tsx
frontend/src/pages/TraineeList.tsx     apps/careerforge/ui/TraineeList.tsx
(no routes contract)                   apps/careerforge/ui/routes.tsx
docker-compose.yml                     deploy/compose.{minimal,observability,full}.yml
                                       deploy/services/{data,platform,observability,auth,local-llm}.yml
(public schema)                        postgres: platform + app_careerforge
(public schema)                        timescale: platform + app_careerforge
(shared labels)                        neo4j: Platform_* / Cf_* prefixes (convention)
(shared collections)                   qdrant: platform__* / app_<name>__* (convention)
```

## Commit-by-commit

| # | Commit  | What changed |
|---|---------|--------------|
| 1 | `7393961` | Move `engine/` → `platform/engine/`. |
| 2 | `afe9e04` | Move `frontend/` → `platform/workbench/` and `channels/` → `platform/channels/`. |
| 3 | `d1b363c` | Delete the standalone `approval-dashboard/` (superseded by the `/governance` routes inside the workbench). |
| 4 | `033561d` | README rewrite + `docs/architecture.md` + `docs/platform-vs-domain.md`. |
| 5 | `c7bc054` | Rename `domains/workforce/` → `apps/careerforge/skills/`. Move the two CareerForge pages from the workbench to `apps/careerforge/ui/`. New `apps/careerforge/ui/routes.tsx` export consumed by `platform/workbench/src/apps.ts` via the `@apps` Vite alias. Engine `config.py` gains `apps_dir` + `apps_enabled`; `api/main.py` lifespan iterates the enabled apps' `skills/` directories. |
| 6 | `96ef051` | Delete the placeholder `domains/{finance,industrial,pharma}/` trees. |
| 7 | `79560cf` | Postgres migration `009_schema_split.sql` + Timescale `003_schema_split.sql` create `platform` and `app_careerforge` schemas and move existing tables via `ALTER TABLE … SET SCHEMA`. Neo4j `003_namespaces.cypher` documents the `Platform_*` / `Cf_*` label convention. `contextforge/namespaces.py` centralises the naming scheme. `PostgresClient` + `TimescaleClient` pin `search_path = platform, app_<apps>, public` on each pool connection. |
| 8 | `4543e53` | Split the root `docker-compose.yml` into `deploy/compose.{minimal,observability,full}.yml` via Compose `include:`. Each service group (`data`, `platform`, `observability`, `auth`, `local-llm`) lives in its own file under `deploy/services/`. The `api` service now mounts `apps/` instead of `domains/` and sets `CONTEXTFORGE_APPS_ENABLED=careerforge`. |
| 9 | `98157b7` | Delete stale root artifacts (old architecture Markdown/HTML/PNG, one-off brief / review notes, scratch `.txt`, the last `domains/` content). Update `docs/architecture.md` "Domain Adapter Pattern" section to "App Pattern". Remove the root `docker-compose.yml`. |
| 10 | *(this commit)* | This summary document. |

## Contract for adding a new app

1. `mkdir -p apps/<name>/{skills,ui,migrations,seed}`.
2. Add SKILL.md files under `apps/<name>/skills/{schema,ingestion,tools,templates,guardrails,channels}/`.
3. Optional: add React views + `ui/routes.tsx` exporting `{ appMeta, navSection, appRoutes }`, and register them in `platform/workbench/src/apps.ts`.
4. Optional: add DDL in `apps/<name>/migrations/` targeting schema `app_<name>` only (platform migrations never touch it).
5. Enable at runtime: `CONTEXTFORGE_APPS_ENABLED=careerforge,<name>`.

The platform stays domain-agnostic. Platform code must never import from `apps/*`.

## Data isolation summary

| Store       | Platform            | CareerForge app                |
|-------------|---------------------|--------------------------------|
| Postgres    | schema `platform`   | schema `app_careerforge`       |
| Timescale   | schema `platform`   | schema `app_careerforge`       |
| Neo4j       | label `Platform_*`  | label `Cf_*`                   |
| Qdrant      | `platform__*`       | `app_careerforge__*`           |
| Redis       | `cf:platform:*`     | `cf:app:careerforge:*`         |

Postgres / Timescale: enforced physically by `search_path` and `ALTER TABLE … SET SCHEMA`.
Qdrant: the four canonical platform collections (`platform__document_chunks`, `platform__entity_embeddings`, `platform__community_summaries`, `platform__skill_catalog`) are exported as constants from `contextforge/db/qdrant.py`; all callsites import them rather than hard-coding names.
Neo4j / Redis: convention documented in `contextforge/namespaces.py`; new writes should adopt the prefix.

## Known follow-ups

- Move existing Neo4j nodes to the prefixed labels (data migration, not just DDL).
- Remove the `_examples/` connector SKILL docs from history once they land under `docs/examples/` (they were deleted in commit 9 with no replacement — reintroduce if operators ask for them).
