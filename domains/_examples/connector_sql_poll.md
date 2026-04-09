---
name: connector_sql_poll
type: connector
domain: _examples
version: "1.0.0"
description: Generic SQL polling connector. Runs a SELECT against any Postgres-compatible database at a fixed interval and emits each row as a record. Supports incremental cursor tracking.
author: human
tags: [connector, sql, postgres, timescale, polling]
source_kind: sql_poll
autostart: false
config:
  dsn: postgresql://contextforge:contextforge@postgres:5432/contextforge
  query: "SELECT id, created_at, payload FROM events WHERE created_at > $1 ORDER BY created_at LIMIT 100"
  cursor_column: created_at
  interval_s: 30
auth:
  type: dsn
  fields: [dsn]
config_schema:
  type: object
  required: [dsn, query]
  properties:
    dsn:           { type: string, description: "asyncpg DSN, e.g. postgresql://user:pass@host:5432/db" }
    query:         { type: string, description: "SELECT to run each interval. If cursor_column is set, must take $1 = last cursor value." }
    cursor_column: { type: string, description: "Column tracked as a high-water mark. Optional." }
    cursor_start:  { description: "Initial cursor value (e.g. ISO timestamp). Optional." }
    interval_s:    { type: number, default: 60 }
    pool_max:      { type: number, default: 2 }
---

# SQL Polling Connector

Periodically runs a `SELECT` against any Postgres-compatible database
(plain Postgres, TimescaleDB, CockroachDB, etc.) and emits each returned
row as a `Record`. Use this for legacy systems whose events live in a
table — audit logs, queues-as-tables, telemetry rollups, CDC fallback.

## Behavior

1. Open an `asyncpg` pool against the configured `dsn`.
2. Loop forever:
   a. If `cursor_column` is set and a high-water mark exists, run
      `query` with the mark bound to `$1`. Otherwise run with no params.
   b. Yield one `Record` per row, with the row dict as `payload`.
   c. Advance the cursor to the maximum value seen for `cursor_column`.
   d. Sleep `interval_s` seconds.
3. On query/network errors, emit an error record and continue —
   transient failures don't crash the supervisor.

## Cursor pattern

For incremental ingestion, design `query` to take the last cursor value
as `$1` and return only newer rows. Example for an `events` table:

```sql
SELECT id, created_at, payload
FROM events
WHERE created_at > $1
ORDER BY created_at
LIMIT 500
```

Set `cursor_column: created_at` and (optionally) `cursor_start` to an
ISO timestamp to bound the first poll.

## Routing through CompositeSink

Rows whose payload includes `entity_type`+`entity_id` will land in the
KG; rows with a numeric `value` go to Timescale; text rows are
embedded into Qdrant. Shape your `SELECT` accordingly to pick a sink.
