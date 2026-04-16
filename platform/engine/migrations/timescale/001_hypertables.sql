-- ContextForge: TimescaleDB Hypertables
-- Migration 001 — entity_telemetry hypertable, 5-min aggregate, retention policy.

-- STATEMENT
-- Raw telemetry hypertable
CREATE TABLE IF NOT EXISTS entity_telemetry (
    time        TIMESTAMPTZ      NOT NULL,
    entity_id   TEXT             NOT NULL,
    channel_id  TEXT             NOT NULL,
    parameter   TEXT             NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    unit        TEXT             NOT NULL,
    quality     TEXT             NOT NULL DEFAULT 'valid'
                    CHECK (quality IN ('valid', 'interpolated', 'sensor_error', 'offline')),
    PRIMARY KEY (time, entity_id, parameter)
);

SELECT create_hypertable(
    'entity_telemetry', 'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_telemetry_entity
    ON entity_telemetry (entity_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_channel
    ON entity_telemetry (channel_id, time DESC);

-- STATEMENT
-- 5-minute continuous aggregate (must run outside transaction)
CREATE MATERIALIZED VIEW IF NOT EXISTS entity_telemetry_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    entity_id,
    parameter,
    AVG(value)   AS avg_value,
    MIN(value)   AS min_value,
    MAX(value)   AS max_value,
    COUNT(*)     AS sample_count
FROM entity_telemetry
GROUP BY bucket, entity_id, parameter
WITH NO DATA;

-- STATEMENT
-- Refresh policy: materialise data older than 10 minutes, look back 1 hour.
SELECT add_continuous_aggregate_policy('entity_telemetry_5min',
    start_offset  => INTERVAL '1 hour',
    end_offset    => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- STATEMENT
-- Retention: drop raw chunks older than 90 days
SELECT add_retention_policy('entity_telemetry',
    INTERVAL '90 days',
    if_not_exists => TRUE
);
