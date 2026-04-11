-- ContextForge: Multi-tenant scoping + per-tenant budgets
-- Migration 007

BEGIN;

-- ─── 1. tenants ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    plan            TEXT NOT NULL DEFAULT 'free'
                        CHECK (plan IN ('free', 'starter', 'pro', 'enterprise')),
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Default tenant for existing data
INSERT INTO tenants (id, slug, name, plan)
VALUES ('00000000-0000-0000-0000-000000000001', 'default', 'Default Tenant', 'enterprise')
ON CONFLICT (slug) DO NOTHING;

-- ─── 2. tenant_budgets ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenant_budgets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period          TEXT NOT NULL DEFAULT 'monthly'
                        CHECK (period IN ('daily', 'weekly', 'monthly')),
    max_tokens      BIGINT NOT NULL DEFAULT 1000000,
    max_cost_usd    NUMERIC(10,2) NOT NULL DEFAULT 50.00,
    max_requests    INT NOT NULL DEFAULT 10000,
    tokens_used     BIGINT NOT NULL DEFAULT 0,
    cost_used_usd   NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    requests_used   INT NOT NULL DEFAULT 0,
    period_start    TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', now()),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, period)
);

-- Budget for default tenant
INSERT INTO tenant_budgets (tenant_id, period, max_tokens, max_cost_usd, max_requests)
VALUES ('00000000-0000-0000-0000-000000000001', 'monthly', 10000000, 500.00, 100000)
ON CONFLICT (tenant_id, period) DO NOTHING;

-- ─── 3. tenant_usage_log ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenant_usage_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL DEFAULT '',
    operation       TEXT NOT NULL DEFAULT 'agent_chat',
    tokens_used     INT NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,4) NOT NULL DEFAULT 0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_log_tenant ON tenant_usage_log (tenant_id, created_at DESC);

-- ─── 4. Add tenant_id to existing tables ───────────────────────────────────
DO $$
BEGIN
    -- agent_configs
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'agent_configs' AND column_name = 'tenant_id') THEN
        ALTER TABLE agent_configs ADD COLUMN tenant_id UUID
            DEFAULT '00000000-0000-0000-0000-000000000001'
            REFERENCES tenants(id);
    END IF;

    -- quality_evaluations
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'quality_evaluations' AND column_name = 'tenant_id') THEN
        ALTER TABLE quality_evaluations ADD COLUMN tenant_id UUID
            DEFAULT '00000000-0000-0000-0000-000000000001'
            REFERENCES tenants(id);
    END IF;

    -- connector_configs
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'connector_configs' AND column_name = 'tenant_id') THEN
        ALTER TABLE connector_configs ADD COLUMN tenant_id UUID
            DEFAULT '00000000-0000-0000-0000-000000000001'
            REFERENCES tenants(id);
    END IF;
END $$;

COMMIT;
