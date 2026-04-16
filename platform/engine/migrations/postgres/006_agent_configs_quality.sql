-- ContextForge: Agent configurations + Quality evaluations
-- Migration 006

BEGIN;

-- ─── 1. agent_configs ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL DEFAULT '',
    domain          TEXT NOT NULL DEFAULT 'industrial',
    model_tier      TEXT NOT NULL DEFAULT 'medium'
                        CHECK (model_tier IN ('small', 'medium', 'large')),
    specialists     JSONB NOT NULL DEFAULT '["retrieval","analysis","action"]',
    guardrails      JSONB NOT NULL DEFAULT '{"pii": true, "toxicity": true, "hallucination": true}',
    budget_limit    NUMERIC(10,2) NOT NULL DEFAULT 5.00,
    max_iterations  INT NOT NULL DEFAULT 15,
    is_default      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_configs_domain ON agent_configs (domain);

-- ─── 2. quality_evaluations ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_evaluations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       TEXT NOT NULL,
    query           TEXT NOT NULL,
    response        TEXT NOT NULL,
    context_snippet TEXT NOT NULL DEFAULT '',
    scores          JSONB NOT NULL DEFAULT '{}',
    overall_score   NUMERIC(3,1) NOT NULL DEFAULT 0,
    issues          JSONB NOT NULL DEFAULT '[]',
    suggestions     JSONB NOT NULL DEFAULT '[]',
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quality_evals_thread ON quality_evaluations (thread_id);
CREATE INDEX IF NOT EXISTS idx_quality_evals_score ON quality_evaluations (overall_score, evaluated_at DESC);

-- ─── 3. improvement_proposals ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS improvement_proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type   TEXT NOT NULL DEFAULT 'unknown',
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    changes         JSONB NOT NULL DEFAULT '[]',
    expected_impact TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'applied')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_status ON improvement_proposals (status, created_at DESC);

COMMIT;
