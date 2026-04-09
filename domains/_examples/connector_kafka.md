---
name: connector_kafka
type: connector
domain: _examples
version: "1.0.0"
description: Kafka consumer connector. Subscribes to one or more topics and emits each message as a record. Supports SASL/PLAIN auth.
author: human
tags: [connector, kafka, streaming, cdc]
source_kind: kafka
autostart: false
config:
  bootstrap_servers: localhost:9092
  topics: [events]
  group_id: contextforge-events
auth:
  type: sasl
  fields: [sasl_username, sasl_password]
config_schema:
  type: object
  required: [bootstrap_servers]
  properties:
    bootstrap_servers:  { type: string, description: "host:port[,host:port,...]" }
    topic:              { type: string, description: "Single topic (alternative to topics)" }
    topics:             { type: array, items: { type: string } }
    group_id:           { type: string }
    auto_offset_reset:  { type: string, default: latest, enum: [latest, earliest] }
    enable_auto_commit: { type: boolean, default: true }
    security_protocol:  { type: string, default: SASL_PLAINTEXT }
    sasl_mechanism:     { type: string, default: PLAIN }
    sasl_username:      { type: string }
    sasl_password:      { type: string }
---

# Kafka Connector

Consumes one or more Kafka topics via `aiokafka` and emits each message
as a `Record`. JSON message values are decoded into the payload dict;
non-JSON bodies are emitted under `{"raw": "..."}`.

`metadata` carries the originating topic, partition, and offset, so
downstream sinks can correlate or replay.

## Install

```
pip install aiokafka
```

The driver lazy-imports `aiokafka`, so the engine still starts when the
package is missing — only `start` requests for kafka connectors will
fail.
