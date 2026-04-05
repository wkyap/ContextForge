# Industrial Domain Adapter

Asset-intensive operations — manufacturing, energy, utilities.

## Directory Structure

| Folder | Purpose |
|--------|---------|
| `schema/` | Knowledge SKILL.md files — Asset, Sensor, WorkOrder, Alarm, Material, Component |
| `ingestion/` | Ingestion SKILL.md files — MQTT streams, OPC-UA, SCADA CSV exports |
| `tools/` | Computation SKILL.md files — anomaly detection, predictive maintenance scoring, RUL estimation |
| `templates/` | Template SKILL.md files — maintenance reports, incident summaries |
| `guardrails/` | Guardrail SKILL.md files — safety-critical threshold validation |
| `channels/` | Channel SKILL.md files — control room alerts, field technician notifications |

## Key Entity Types

- **Asset** — pumps, turbines, compressors, conveyor lines
- **Sensor** — vibration, temperature, pressure, flow rate
- **WorkOrder** — planned/unplanned maintenance tasks
- **Alarm** — threshold breaches, anomaly detections
- **Material** — spare parts, consumables
- **Component** — sub-assemblies within assets

## Data Sources

- MQTT real-time sensor streams
- OPC-UA historians
- CMMS exports (SAP PM, Maximo)
