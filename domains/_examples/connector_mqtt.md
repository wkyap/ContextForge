---
name: connector_mqtt
type: connector
domain: _examples
version: "1.0.0"
description: Generic MQTT broker connector. Subscribes to one or more topics and emits each message as an ingestion record.
author: human
tags: [connector, mqtt, streaming, iot]
source_kind: mqtt
auth:
  type: basic
  fields: [username, password]
config_schema:
  type: object
  required: [host, topics]
  properties:
    host:     { type: string, default: localhost }
    port:     { type: integer, default: 1883 }
    username: { type: string }
    password: { type: string }
    topics:
      type: array
      items: { type: string }
      description: "MQTT topic filters to subscribe to (e.g. ['sensors/+/temp'])"
---

# MQTT Connector

Subscribes to one or more MQTT topics on a broker and yields every incoming
message as a `Record` into the connector runtime.

## Behavior

1. Connect to the configured broker using `aiomqtt`.
2. Subscribe to all `topics` in the config.
3. For each message, attempt to JSON-decode the payload. If successful and
   the result is a dict, use it as the record payload; otherwise wrap it as
   `{"value": <decoded>}`. Non-JSON payloads are wrapped as `{"raw": <utf8 string>}`.
4. Stream records until the supervisor cancels the task.

## Example config

```json
{
  "host": "broker.local",
  "port": 1883,
  "topics": ["sensors/+/temp", "sensors/+/humidity"]
}
```
