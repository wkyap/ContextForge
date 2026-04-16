-- ContextForge: PostgreSQL App Tables
-- Migration 001 — Foundation tables for skills, governance, agents, and pipelines.

BEGIN;

-- ─── 1. skills ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    type            TEXT NOT NULL CHECK (type IN (
                        'knowledge', 'ingestion', 'computation',
                        'template', 'guardrail', 'channel'
                    )),
    description     TEXT NOT NULL DEFAULT '',
    file_path       TEXT NOT NULL,
    author          TEXT NOT NULL DEFAULT 'human',
    version         INT  NOT NULL DEFAULT 1,
    domain          TEXT,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skills_type   ON skills (type);
CREATE INDEX IF NOT EXISTS idx_skills_domain ON skills (domain) WHERE domain IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_skills_active ON skills (active) WHERE active = TRUE;

-- ─── 2. agent_sessions ──────────────────────────────────────────────────────
-- LangGraph PostgresSaver creates its own checkpoint tables at runtime.
-- This table stores lightweight session metadata for the API layer.
CREATE TABLE IF NOT EXISTS agent_sessions (
    thread_id       TEXT NOT NULL,
    user_id         TEXT,
    title           TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_user ON agent_sessions (user_id, created_at DESC)
    WHERE user_id IS NOT NULL;

-- ─── 3. proposals ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL CHECK (type IN (
                        'schema_evolution', 'tool_generation',
                        'strategy_optimization', 'prompt_revision',
                        'guardrails_adjustment', 'quality_fix'
                    )),
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    proposed_by     TEXT NOT NULL,
    content         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'modified')),
    approver_id     TEXT,
    approval_reason TEXT,
    autonomy_level  INT NOT NULL DEFAULT 0 CHECK (autonomy_level >= 0 AND autonomy_level <= 4),
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_proposals_status   ON proposals (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_proposer ON proposals (proposed_by, status);

-- ─── 4. audit_log ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id         TEXT NOT NULL DEFAULT 'system',
    action_type     TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT,
    change_details  JSONB NOT NULL DEFAULT '{}',
    result          TEXT NOT NULL CHECK (result IN ('success', 'failure', 'escalated_to_human')),
    reason          TEXT,
    ip_address      INET,
    correlation_id  UUID
);

CREATE INDEX IF NOT EXISTS idx_audit_log_time     ON audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user     ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log (resource_type, resource_id);

-- ─── 5. autonomy_levels ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS autonomy_levels (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    function_name           TEXT NOT NULL UNIQUE,
    autonomy_level          INT  NOT NULL DEFAULT 0
                                CHECK (autonomy_level >= 0 AND autonomy_level <= 4),
    proposal_count          INT  NOT NULL DEFAULT 0,
    approval_count          INT  NOT NULL DEFAULT 0,
    approval_rate           FLOAT NOT NULL DEFAULT 0
                                CHECK (approval_rate >= 0 AND approval_rate <= 1),
    last_rejection_at       TIMESTAMPTZ,
    promoted_at             TIMESTAMPTZ,
    promoted_by             TEXT,
    last_audit_sample_result TEXT CHECK (last_audit_sample_result IN ('pass', 'fail', 'unclear'))
);

-- ─── 6. pipelines ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipelines (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL UNIQUE,
    description         TEXT NOT NULL DEFAULT '',
    type                TEXT NOT NULL CHECK (type IN ('stream', 'document', 'api', 'batch')),
    config              JSONB NOT NULL DEFAULT '{}',
    domain              TEXT,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    schedule_cron       TEXT,
    last_run_at         TIMESTAMPTZ,
    last_run_status     TEXT CHECK (last_run_status IN ('success', 'failure', 'running', 'queued')),
    next_run_at         TIMESTAMPTZ,
    error_count_24h     INT NOT NULL DEFAULT 0,
    records_processed_24h INT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipelines_enabled ON pipelines (enabled, domain);

COMMIT;
