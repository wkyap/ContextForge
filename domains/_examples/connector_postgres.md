---
name: connector_postgres
type: connector
domain: _examples
version: 1
description: Generic PostgreSQL connector — pulls rows from a configured table into the ingestion pipeline.
author: human
tags: [connector, sql, postgres, example]
source_kind: database
auth:
  type: basic
  fields: [host, port, user, password, database]
config_schema:
  type: object
  required: [host, database, table]
  properties:
    host: { type: string }
    port: { type: integer, default: 5432 }
    database: { type: string }
    table: { type: string }
    where: { type: string, description: "Optional SQL WHERE clause" }
    batch_size: { type: integer, default: 1000 }
---

# PostgreSQL Connector

This connector reads rows from a Postgres table in batches and emits them as
records into the ingestion pipeline. It is the canonical example of the
`connector` SKILL type.

## Behavior

1. Open a connection using credentials from the configured secret store.
2. Issue `SELECT * FROM {table} WHERE {where}` paginated by `batch_size`.
3. Yield each row as a dict to downstream `ingestion` skills.
4. Emit a final checkpoint event so the pipeline can resume on failure.

## Notes for authors

`connector` skills must declare:

- `source_kind` — one of `database`, `api`, `stream`, `file`, `messaging`
- `auth` — auth model (`basic`, `oauth2`, `api_key`, `none`)
- `config_schema` — JSON Schema for runtime configuration
