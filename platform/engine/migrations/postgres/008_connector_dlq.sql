-- Phase 5: connector dead-letter queue.
--
-- Records that fail to be written to a sink (or that crash the connector
-- mid-stream) are persisted here so operators can inspect and replay them
-- instead of silently dropping data.
--
-- A row's lifecycle:
--   pending  → just inserted, waiting for triage / replay
--   replayed → operator replayed it successfully
--   ignored  → operator marked it as not-recoverable
--
-- Schema is intentionally minimal — payload + reason + provenance.

CREATE TABLE IF NOT EXISTS connector_dlq (
    id              BIGSERIAL PRIMARY KEY,
    connector_name  TEXT NOT NULL,
    sink_name       TEXT,
    source          TEXT,
    payload         JSONB NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    error           TEXT NOT NULL,
    record_ts       DOUBLE PRECISION,
    failed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL DEFAULT 'pending',
    replayed_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_connector_dlq_connector ON connector_dlq (connector_name);
CREATE INDEX IF NOT EXISTS idx_connector_dlq_status    ON connector_dlq (status);
CREATE INDEX IF NOT EXISTS idx_connector_dlq_failed_at ON connector_dlq (failed_at DESC);
