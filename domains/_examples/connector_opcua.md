---
name: connector_opcua
type: connector
domain: _examples
version: "1.0.0"
description: OPC-UA polling connector. Reads a list of node ids on a fixed interval and emits each value as an entity-shaped record (suitable for TimescaleSink via CompositeSink).
author: human
tags: [connector, opcua, industrial, scada, plc]
source_kind: opcua
autostart: false
config:
  url: opc.tcp://localhost:4840
  nodes: ["ns=2;i=2", "ns=2;i=3"]
  interval_s: 5
auth:
  type: basic
  fields: [username, password]
config_schema:
  type: object
  required: [url, nodes]
  properties:
    url:        { type: string, description: "OPC-UA endpoint, e.g. opc.tcp://host:4840" }
    nodes:      { type: array, items: { type: string }, description: "Node ids to poll" }
    interval_s: { type: number, default: 5 }
    username:   { type: string }
    password:   { type: string }
---

# OPC-UA Connector

Polls a fixed list of OPC-UA node ids on the configured interval and
emits one `Record` per node per cycle. Each payload is shaped as
`{entity_id: <node_id>, parameter: "value", value: <reading>}` so the
`CompositeSink` automatically routes it to `TimescaleSink`.

## Install

```
pip install asyncua
```

The driver lazy-imports `asyncua`, so the engine still starts when the
package is missing — only `start` requests for opcua connectors will
fail.

Subscriptions (push-based monitored items) are not yet supported; use
this for steady-cadence sampling. For high-frequency sources, prefer a
dedicated OPC-UA → MQTT/Kafka bridge and the corresponding connector.
