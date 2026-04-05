---
name: observation
type: knowledge
domain: healthcare
version: 1
description: "Clinical observation — vitals, lab results, assessments, clinical notes"
author: human
tags: [entity, observation, vitals, labs, measurements, core]
entity_type: Observation
properties:
  - name: observation_id
    type: string
    required: true
    description: "Unique observation identifier"
  - name: status
    type: string
    required: true
    description: "Status (registered, preliminary, final, amended, cancelled)"
  - name: category
    type: string
    required: true
    description: "Category (vital-signs, laboratory, imaging, social-history, exam)"
  - name: code
    type: string
    required: true
    description: "LOINC or SNOMED code for the observation type"
  - name: code_display
    type: string
    required: false
    description: "Human-readable name (e.g., Heart Rate, Hemoglobin)"
  - name: value
    type: float
    required: false
    description: "Numeric value (for quantitative observations)"
  - name: value_string
    type: string
    required: false
    description: "String value (for qualitative observations or notes)"
  - name: unit
    type: string
    required: false
    description: "Unit of measurement (UCUM coded, e.g., beats/min, mmol/L)"
  - name: effective_time
    type: datetime
    required: true
    description: "When the observation was made"
  - name: reference_range_low
    type: float
    required: false
    description: "Normal range lower bound"
  - name: reference_range_high
    type: float
    required: false
    description: "Normal range upper bound"
  - name: interpretation
    type: string
    required: false
    description: "Interpretation flag (normal, abnormal, critical, high, low)"
  - name: performer
    type: string
    required: false
    description: "Who made the observation"
relationships:
  - type: OBSERVATION_FOR
    target: Patient
    cardinality: many_to_one
  - type: DURING_ENCOUNTER
    target: Encounter
    cardinality: many_to_one
temporal: true
---

# Observation

Observations capture clinical measurements, test results, and assessments. They are the most numerous entity type in healthcare and the primary data source for time-series telemetry.

## Categories

| Category | Examples | TimescaleDB |
|----------|----------|-------------|
| `vital-signs` | Heart rate, BP, SpO2, temperature, RR | Yes — stream to entity_telemetry |
| `laboratory` | Hemoglobin, creatinine, WBC, CRP | Yes — stream to entity_telemetry |
| `imaging` | X-ray reports, CT findings | No — text in KG only |
| `social-history` | Smoking status, alcohol use | No — KG only |
| `exam` | Physical examination findings | No — KG only |

## Vital Signs → TimescaleDB Bridge

Numeric vital-signs observations are dual-written:
1. **Neo4j** — entity node with full metadata and relationships
2. **TimescaleDB** — `entity_telemetry` row for efficient time-series queries

The `parameter` in TimescaleDB maps to the observation's `code_display` (lowercase, underscored).

| Observation | Parameter | Unit | Typical Range |
|-------------|-----------|------|---------------|
| Heart Rate | `heart_rate` | beats/min | 60-100 |
| Systolic BP | `systolic_bp` | mmHg | 90-140 |
| Diastolic BP | `diastolic_bp` | mmHg | 60-90 |
| SpO2 | `spo2` | % | 94-100 |
| Temperature | `temperature` | Cel | 36.1-37.2 |
| Respiratory Rate | `respiratory_rate` | breaths/min | 12-20 |

## Agent Notes

- When asked about trends, query TimescaleDB aggregates rather than KG history
- Critical observations (`interpretation = "critical"`) should trigger alerts
- Always include units when presenting values to clinicians
- Lab results may have multiple components (e.g., FBC has Hb, WBC, Platelets)
