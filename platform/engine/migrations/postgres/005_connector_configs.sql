-- Phase 2.5: persisted connector configurations.
--
-- Each row represents a named connector instance the operator wants the
-- engine to manage. On startup the lifespan reads `enabled = true` rows and
-- asks the supervisor to start them. POSTing /api/v1/connectors/configs
-- inserts/updates rows here.

CREATE TABLE IF NOT EXISTS connector_configs (
    name         TEXT PRIMARY KEY,
    source_kind  TEXT NOT NULL,
    config       JSONB NOT NULL DEFAULT '{}'::jsonb,
    sink         TEXT,                       -- override sink name (kg/timescale/vector/composite/logging); NULL = supervisor default
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_connector_configs_kind     ON connector_configs (source_kind);
CREATE INDEX IF NOT EXISTS idx_connector_configs_enabled  ON connector_configs (enabled);
