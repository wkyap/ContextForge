-- ═══════════════════════════════════════════════════════
-- CareerForge — Trainee Metrics Hypertable
-- Time-series tracking for trainee progress
-- ═══════════════════════════════════════════════════════

-- STATEMENT
CREATE TABLE IF NOT EXISTS trainee_metrics (
    time            TIMESTAMPTZ NOT NULL,
    trainee_id      VARCHAR(100) NOT NULL,
    programme_id    VARCHAR(100),
    metric          VARCHAR(50) NOT NULL,
    value           DOUBLE PRECISION NOT NULL,
    metadata        JSONB DEFAULT '{}'
);

SELECT create_hypertable('trainee_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_tm_trainee ON trainee_metrics (trainee_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_tm_metric ON trainee_metrics (metric, time DESC);
CREATE INDEX IF NOT EXISTS idx_tm_programme ON trainee_metrics (programme_id, time DESC);

-- STATEMENT
-- Weekly aggregate for dashboard charts (must run outside transaction)
CREATE MATERIALIZED VIEW IF NOT EXISTS trainee_metrics_weekly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('7 days', time) AS bucket,
    trainee_id,
    programme_id,
    metric,
    avg(value) AS avg_value,
    max(value) AS max_value,
    min(value) AS min_value,
    count(*) AS sample_count
FROM trainee_metrics
GROUP BY bucket, trainee_id, programme_id, metric;

-- STATEMENT
-- Retain trainee metrics for 2 years (career programmes track long-term)
SELECT add_retention_policy('trainee_metrics', INTERVAL '730 days', if_not_exists => TRUE);
