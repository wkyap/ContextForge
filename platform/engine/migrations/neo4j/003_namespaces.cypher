// ContextForge: Neo4j namespace convention
// Migration 003 — declares the label/property prefix contract for the
// platform/app data-isolation boundary per docs/platform-vs-domain.md.
//
// Neo4j has no schema concept; isolation is by *label prefix* convention:
//
//   Platform_*   — nodes owned by the platform engine
//   Cf_*         — nodes owned by the CareerForge app
//
// Existing entity nodes use the generic :Entity label plus a `_type` property
// and are not relabeled by this migration. New writes should carry a prefixed
// label in addition to :Entity, e.g. `(:Entity:Platform_Connector { … })`.
//
// This file is intentionally free of DDL — it documents intent and gives the
// migration runner a numbered marker so future label migrations can build on
// the convention.

// STATEMENT sentinel (no-op) so the runner records this migration.
MATCH (n) WHERE false RETURN n LIMIT 0;
