-- ContextForge: Additional tables for new API routes
-- Migration 004 — onboarding plans, pipeline runs

BEGIN;

-- ─── 1. onboarding_plans ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name     TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    plan            JSONB NOT NULL DEFAULT '{}',
    validation      JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'approved', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_plans_status ON onboarding_plans (status, created_at DESC);

-- ─── 2. pipeline_runs ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'success', 'failure')),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    records_processed INT NOT NULL DEFAULT 0,
    error_count     INT NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline ON pipeline_runs (pipeline_id, started_at DESC);

COMMIT;
