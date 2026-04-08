---
name: connector_http_poll
type: connector
domain: _examples
version: "1.0.0"
description: Periodic HTTP GET connector. Polls a REST endpoint at a fixed interval and emits each response as a record.
author: human
tags: [connector, http, rest, fhir, polling]
source_kind: http_poll
auth:
  type: any
  fields: [bearer_token, username, password, headers]
config_schema:
  type: object
  required: [url]
  properties:
    url:          { type: string, description: "Endpoint to poll" }
    method:       { type: string, default: GET }
    interval_s:   { type: number, default: 60 }
    timeout_s:    { type: number, default: 30 }
    params:       { type: object, description: "Query string params" }
    headers:      { type: object, description: "Extra request headers" }
    bearer_token: { type: string, description: "If set, sent as Authorization: Bearer <token>" }
    username:     { type: string }
    password:     { type: string }
---

# HTTP Polling Connector

Polls any REST endpoint at a fixed interval and emits the JSON response as
a single `Record` per poll. Designed for sources that don't support
webhooks or streaming — REST APIs, FHIR resource endpoints, vendor status
pages, weather APIs, etc.

## Behavior

1. Open a long-lived `httpx.AsyncClient` with the configured auth/headers.
2. Loop forever:
   a. Issue the configured request.
   b. JSON-decode the response. Non-dict bodies are wrapped as `{"items": <body>}`.
   c. Yield a `Record` with the response payload and `metadata.url` set.
   d. Sleep `interval_s` seconds.
3. On HTTP/network errors, emit an error record (with `payload.error` set)
   and continue polling — the supervisor does not crash on transient failures.

## Example config (FHIR Patient endpoint)

```json
{
  "url": "https://hapi.fhir.org/baseR4/Patient",
  "params": {"_count": 10, "_format": "json"},
  "interval_s": 300,
  "bearer_token": "..."
}
```
