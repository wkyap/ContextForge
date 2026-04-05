---
name: encounter
type: knowledge
domain: healthcare
version: 1
description: "Clinical encounter — admissions, ED visits, outpatient appointments"
author: human
tags: [entity, encounter, admission, visit, core]
entity_type: Encounter
properties:
  - name: encounter_id
    type: string
    required: true
    description: "Unique encounter identifier"
  - name: status
    type: string
    required: true
    description: "Current status (planned, arrived, triaged, in-progress, onleave, finished, cancelled)"
  - name: class
    type: string
    required: true
    description: "Classification (inpatient, outpatient, emergency, virtual)"
  - name: type_code
    type: string
    required: false
    description: "Encounter type (SNOMED coded)"
  - name: priority
    type: string
    required: false
    description: "Admission priority (elective, emergency, urgent)"
  - name: start_time
    type: datetime
    required: true
    description: "When the encounter began"
  - name: end_time
    type: datetime
    required: false
    description: "When the encounter ended (null if ongoing)"
  - name: ward
    type: string
    required: false
    description: "Current or last ward/location"
  - name: bed
    type: string
    required: false
    description: "Bed assignment"
  - name: attending_clinician
    type: string
    required: false
    description: "Responsible clinician name or ID"
  - name: discharge_disposition
    type: string
    required: false
    description: "How the patient left (home, transfer, deceased, etc.)"
  - name: reason_for_visit
    type: string
    required: false
    description: "Chief complaint or reason for encounter"
relationships:
  - type: ENCOUNTER_FOR
    target: Patient
    cardinality: many_to_one
  - type: HAS_OBSERVATION
    target: Observation
    cardinality: one_to_many
  - type: HAS_CONDITION
    target: Condition
    cardinality: one_to_many
  - type: HAS_PROCEDURE
    target: Procedure
    cardinality: one_to_many
temporal: true
---

# Encounter

An encounter represents a period of healthcare interaction between a patient and a healthcare provider. This includes admissions, ED visits, outpatient appointments, and virtual consultations.

## Status Lifecycle

```
planned → arrived → triaged → in-progress → finished
                                    ↓
                                onleave → in-progress
```

## FHIR R4 Mapping

| FHIR Path | Property |
|-----------|----------|
| `Encounter.identifier[0].value` | `encounter_id` |
| `Encounter.status` | `status` |
| `Encounter.class.code` | `class` |
| `Encounter.type[0].coding[0]` | `type_code` |
| `Encounter.period.start` | `start_time` |
| `Encounter.period.end` | `end_time` |
| `Encounter.location[0].location` | `ward` |
| `Encounter.reasonCode[0].text` | `reason_for_visit` |

## Agent Notes

- Active encounters have `status = "in-progress"` and `end_time = null`
- Length of stay = `end_time - start_time` (only compute for finished encounters)
- When summarising a patient, prioritise the most recent active encounter
- Ward transfers create relationship changes, not new encounter nodes
