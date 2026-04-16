"""Startup migration runner — applies SQL/Cypher migrations and bootstraps Qdrant collections."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from contextforge.db.neo4j import Neo4jClient
from contextforge.db.postgres import PostgresClient
from contextforge.db.qdrant import QdrantClient
from contextforge.db.timescale import TimescaleClient

logger = logging.getLogger(__name__)

_MIGRATIONS_ROOT = Path(__file__).resolve().parents[2] / "migrations"
_PG_DIR = _MIGRATIONS_ROOT / "postgres"
_TS_DIR = _MIGRATIONS_ROOT / "timescale"
_NEO4J_DIR = _MIGRATIONS_ROOT / "neo4j"

# Repo-level apps/ directory (platform/engine/contextforge/db/migrations.py
# → parents[4] is the repo root).
_REPO_ROOT = Path(__file__).resolve().parents[4]


async def _run_sql_migrations(
    pool_execute: Callable[[str], Awaitable[Any]],
    migrations_dir: Path,
    label: str,
) -> None:
    """Execute .sql files in sorted order.

    Each file is split on ``-- STATEMENT`` markers or semicolons so that
    statements that cannot run inside a transaction (e.g. TimescaleDB
    continuous aggregates) are executed individually.
    """
    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        logger.warning("No SQL migrations found in %s", migrations_dir)
        return
    for path in sql_files:
        logger.info("[%s] Applying %s …", label, path.name)
        sql = path.read_text(encoding="utf-8")

        # Split on explicit marker or fall back to whole-file execution
        if "-- STATEMENT" in sql:
            statements = [
                s.strip()
                for s in sql.split("-- STATEMENT")
                if s.strip() and not s.strip().startswith("--")
            ]
        else:
            statements = [sql]

        for stmt in statements:
            try:
                await pool_execute(stmt)
            except Exception as exc:
                err = str(exc).lower()
                if "already exists" in err or "if not exists" in err:
                    logger.debug("[%s] Skipped (already exists): %.80s…", label, stmt)
                else:
                    raise
        logger.info("[%s] ✓ %s applied", label, path.name)


async def _run_cypher_migrations(
    neo4j: Neo4jClient, migrations_dir: Path = _NEO4J_DIR
) -> None:
    """Execute .cypher files in sorted order, one statement at a time."""
    cypher_files = sorted(migrations_dir.glob("*.cypher"))
    if not cypher_files:
        logger.warning("No Cypher migrations found in %s", migrations_dir)
        return
    for path in cypher_files:
        logger.info("[Neo4j] Applying %s …", path.name)
        text = path.read_text(encoding="utf-8")
        # Split on semicolons, skip blank/comment-only lines.
        statements = [
            s.strip()
            for s in text.split(";")
            if s.strip() and not all(
                line.strip().startswith("//") or line.strip() == ""
                for line in s.strip().splitlines()
            )
        ]
        for stmt in statements:
            try:
                await neo4j.execute_cypher(stmt)
            except Exception as exc:
                # "already exists" is expected for IF NOT EXISTS migrations.
                if "already exists" in str(exc).lower():
                    logger.debug("[Neo4j] Skipped (already exists): %.80s", stmt)
                else:
                    raise
        logger.info("[Neo4j] ✓ %s applied", path.name)


async def run_all_migrations(
    postgres: PostgresClient,
    timescale: TimescaleClient,
    neo4j: Neo4jClient,
    qdrant: QdrantClient,
    *,
    apps_root: Path | None = None,
    enabled_apps: list[str] | None = None,
) -> None:
    """Run every migration step in order. Called once during app startup.

    Platform migrations under ``platform/engine/migrations/`` run first. Then,
    for each app listed in ``enabled_apps``, migrations under
    ``<apps_root>/<app>/migrations/{postgres,timescale,neo4j}/`` run in order.
    Apps-aware arguments are optional so existing callers (tests) keep working.
    """
    logger.info("═══ Starting database migrations ═══")

    # 1. Platform PostgreSQL
    await _run_sql_migrations(postgres.execute, _PG_DIR, "Postgres")

    # 2. Platform TimescaleDB
    await _run_sql_migrations(timescale.execute, _TS_DIR, "Timescale")

    # 3. Platform Neo4j
    await _run_cypher_migrations(neo4j, _NEO4J_DIR)

    # 4. Per-app migrations (iterated in the order apps were enabled)
    for name in enabled_apps or []:
        root = (apps_root or _REPO_ROOT / "apps") / name / "migrations"
        if (root / "postgres").exists():
            await _run_sql_migrations(
                postgres.execute, root / "postgres", f"Postgres[{name}]"
            )
        if (root / "timescale").exists():
            await _run_sql_migrations(
                timescale.execute, root / "timescale", f"Timescale[{name}]"
            )
        if (root / "neo4j").exists():
            await _run_cypher_migrations(neo4j, root / "neo4j")

    # 5. Qdrant collections
    logger.info("[Qdrant] Ensuring collections …")
    await qdrant.ensure_collections()
    logger.info("[Qdrant] ✓ Collections ready")

    logger.info("═══ All migrations complete ═══")
