-- ContextForge: Platform / App schema split
-- Migration 009 — introduce `platform` and `app_careerforge` schemas per
-- docs/platform-vs-domain.md data-isolation contract.
--
-- Tables previously created in the `public` schema are migrated into their
-- target schema via ALTER TABLE ... SET SCHEMA. The database-level search_path
-- is updated so existing, unqualified SQL in the Python clients keeps working.
--
-- Statements are separated with `-- STATEMENT` because ALTER DATABASE cannot
-- run inside the implicit transaction wrapping a multi-statement execute().

-- STATEMENT
CREATE SCHEMA IF NOT EXISTS platform;

-- STATEMENT
CREATE SCHEMA IF NOT EXISTS app_careerforge;

-- STATEMENT
ALTER DATABASE contextforge SET search_path = platform, app_careerforge, public;

-- ─── CareerForge app tables ──────────────────────────────────────────────────
-- STATEMENT
ALTER TABLE IF EXISTS public.programmes       SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.trainees         SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.courses          SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.employers        SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.job_openings     SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.applications     SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.placements       SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.documents        SET SCHEMA app_careerforge;
-- STATEMENT
ALTER TABLE IF EXISTS public.matching_results SET SCHEMA app_careerforge;

-- ─── Platform tables ─────────────────────────────────────────────────────────
-- STATEMENT
ALTER TABLE IF EXISTS public.skills                SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.agent_sessions        SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.proposals             SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.audit_log             SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.autonomy_levels       SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.pipelines             SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.onboarding_plans      SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.pipeline_runs         SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.connector_configs     SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.agent_configs         SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.quality_evaluations   SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.improvement_proposals SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.tenants               SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.tenant_budgets        SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.tenant_usage_log      SET SCHEMA platform;
-- STATEMENT
ALTER TABLE IF EXISTS public.connector_dlq         SET SCHEMA platform;
