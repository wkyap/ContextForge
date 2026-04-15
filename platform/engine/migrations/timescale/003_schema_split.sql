-- ContextForge: TimescaleDB Platform / App schema split
-- Migration 003 — mirrors the Postgres 009 schema split on the Timescale side.

-- STATEMENT
CREATE SCHEMA IF NOT EXISTS platform;

-- STATEMENT
CREATE SCHEMA IF NOT EXISTS app_careerforge;

-- STATEMENT
ALTER DATABASE contextforge_ts SET search_path = platform, app_careerforge, public;

-- ─── Platform hypertables ────────────────────────────────────────────────────
-- STATEMENT
ALTER TABLE IF EXISTS public.entity_telemetry SET SCHEMA platform;

-- ─── CareerForge app hypertables ─────────────────────────────────────────────
-- STATEMENT
ALTER TABLE IF EXISTS public.trainee_metrics  SET SCHEMA app_careerforge;
