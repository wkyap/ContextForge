"""Startup migration runner — applies SQL/Cypher migrations and bootstraps Qdrant collections."""

from __future__ import annotations

import logging
from pathlib import Path

from contextforge.db.neo4j import Neo4jClient
from contextforge.db.postgres import PostgresClient
from contextforge.db.qdrant import QdrantClient
from contextforge.db.timescale import TimescaleClient

logger = logging.getLogger(__name__)

# Paths relative to the repository root (engine/migrations/…).
_MIGRATIONS_ROOT = Path(__file__).resolve().parents[2] / "migrations"
_PG_DIR = _MIGRATIONS_ROOT / "postgres"
_TS_DIR = _MIGRATIONS_ROOT / "timescale"
_NEO4J_DIR = _MIGRATIONS_ROOT / "neo4j"


async def _run_sql_migrations(pool_execute, migrations_dir: Path, label: str) -> None:
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


async def _run_cypher_migrations(neo4j: Neo4jClient) -> None:
    """Execute .cypher files in sorted order, one statement at a time."""
    cypher_files = sorted(_NEO4J_DIR.glob("*.cypher"))
    if not cypher_files:
        logger.warning("No Cypher migrations found in %s", _NEO4J_DIR)
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
) -> None:
    """Run every migration step in order. Called once during app startup."""
    logger.info("═══ Starting database migrations ═══")

    # 1. PostgreSQL app tables
    await _run_sql_migrations(postgres.execute, _PG_DIR, "Postgres")

    # 2. TimescaleDB hypertables
    await _run_sql_migrations(timescale.execute, _TS_DIR, "Timescale")

    # 3. Neo4j schema
    await _run_cypher_migrations(neo4j)

    # 4. Qdrant collections
    logger.info("[Qdrant] Ensuring collections …")
    await qdrant.ensure_collections()
    logger.info("[Qdrant] ✓ Collections ready")

    logger.info("═══ All migrations complete ═══")
