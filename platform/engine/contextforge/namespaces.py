"""Platform / app namespace constants.

Per docs/platform-vs-domain.md the data stores are shared across platform and
apps but separated by schema / label / key-prefix. This module centralises the
naming convention so new code can reach for one import instead of hard-coding
strings.

| Store       | Platform            | App (e.g. careerforge)        |
|-------------|---------------------|-------------------------------|
| Postgres    | schema `platform`   | schema `app_<name>`           |
| Timescale   | schema `platform`   | schema `app_<name>`           |
| Neo4j       | label `Platform_*`  | label `Cf_*` / `App<Name>_*`  |
| Qdrant      | `platform__*`       | `app_<name>__*`               |
| Redis       | `cf:platform:*`     | `cf:app:<name>:*`             |
"""

from __future__ import annotations

# ─── Postgres / Timescale ─────────────────────────────────────────
PLATFORM_PG_SCHEMA: str = "platform"
APP_PG_SCHEMA_PREFIX: str = "app_"


def app_pg_schema(app_name: str) -> str:
    return f"{APP_PG_SCHEMA_PREFIX}{app_name}"


# ─── Neo4j label prefixes ─────────────────────────────────────────
PLATFORM_NEO4J_LABEL_PREFIX: str = "Platform_"
# Default per-app label prefix is the first two letters of the app name
# capitalised followed by an underscore (e.g. careerforge → "Cf_"). Apps with
# unusual names can override via configuration.
APP_NEO4J_LABEL_PREFIXES: dict[str, str] = {
    "careerforge": "Cf_",
}


def app_neo4j_label_prefix(app_name: str) -> str:
    return APP_NEO4J_LABEL_PREFIXES.get(
        app_name, f"{app_name[:1].upper()}{app_name[1:2].lower()}_"
    )


# ─── Qdrant collection prefixes ───────────────────────────────────
PLATFORM_QDRANT_PREFIX: str = "platform__"
APP_QDRANT_PREFIX_TEMPLATE: str = "app_{name}__"


def app_qdrant_prefix(app_name: str) -> str:
    return APP_QDRANT_PREFIX_TEMPLATE.format(name=app_name)


# ─── Redis key prefixes ───────────────────────────────────────────
PLATFORM_REDIS_PREFIX: str = "cf:platform:"
APP_REDIS_PREFIX_TEMPLATE: str = "cf:app:{name}:"


def app_redis_prefix(app_name: str) -> str:
    return APP_REDIS_PREFIX_TEMPLATE.format(name=app_name)
