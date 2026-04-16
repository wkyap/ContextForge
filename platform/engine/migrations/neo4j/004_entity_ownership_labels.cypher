// ContextForge: Neo4j entity ownership labels
// Migration 004 — write-side ownership attribution for the platform/app split.
//
// As of this migration, every :Entity node carries an additional "ownership"
// label plus an `_app` property:
//
//   Platform_Entity  + _app = null          — platform-owned (skills, connectors, …)
//   Cf_Entity        + _app = 'careerforge' — CareerForge-owned
//
// New writes go through `TemporalGraph.create_entity(app=…)` which sets both
// the label and the property. This migration is a safety-net backfill for any
// pre-existing `:Entity` nodes left over from dev/staging data: since
// CareerForge was the only app before this migration, unlabelled nodes are
// attributed to it.
//
// Idempotent: a re-run finds nothing to update on an already-migrated graph.
// Clean-start deployments (no existing entities) see it as a no-op.

MATCH (e:Entity)
WHERE NOT (e:Platform_Entity) AND NOT (e:Cf_Entity)
SET e:Cf_Entity, e._app = 'careerforge';
