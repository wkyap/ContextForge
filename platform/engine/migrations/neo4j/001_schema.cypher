// ContextForge: Neo4j Temporal Knowledge Graph Schema
// Migration 001 — Constraints, indexes, and full-text search.

// ─── 1. Uniqueness constraint ────────────────────────────────────────────────
CREATE CONSTRAINT unique_entity_id IF NOT EXISTS
FOR (e:Entity)
REQUIRE e.id IS UNIQUE;

// ─── 2. Property indexes ─────────────────────────────────────────────────────
CREATE INDEX idx_entity_is_current IF NOT EXISTS
FOR (e:Entity) ON (e._is_current);

CREATE INDEX idx_entity_type IF NOT EXISTS
FOR (e:Entity) ON (e._type);

CREATE INDEX idx_entity_valid_from IF NOT EXISTS
FOR (e:Entity) ON (e._valid_from);

CREATE INDEX idx_entity_valid_to IF NOT EXISTS
FOR (e:Entity) ON (e._valid_to);

CREATE INDEX idx_entity_community_id IF NOT EXISTS
FOR (e:Entity) ON (e._community_id);

CREATE INDEX idx_entity_updated_at IF NOT EXISTS
FOR (e:Entity) ON (e._updated_at);

// ─── 3. Full-text search index ───────────────────────────────────────────────
// Note: fulltext indexes use a separate CREATE syntax and cannot use IF NOT EXISTS
// in all Neo4j versions.  The migration runner should catch "already exists" errors.
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
FOR (e:Entity)
ON EACH [e.name, e.description, e.type];
