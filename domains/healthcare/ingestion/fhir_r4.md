---
name: fhir_r4_ingester
type: ingestion
domain: healthcare
version: 1
description: "FHIR R4 Bundle ingestion — parse Patient, Encounter, Observation, Condition, MedicationRequest"
author: human
tags: [ingestion, fhir, hl7, interoperability]
source_type: api
format: fhir_r4
mapping:
  Patient: patient
  Encounter: encounter
  Observation: observation
  Condition: condition
  MedicationRequest: medication
schedule: null
---

# FHIR R4 Ingester

Parses FHIR R4 Bundles (JSON) and maps resources to ContextForge entity types.

## Supported Resource Types

| FHIR Resource | Entity Type | Status |
|---------------|-------------|--------|
| Patient | Patient | Supported |
| Encounter | Encounter | Supported |
| Observation | Observation | Supported |
| Condition | Condition | Supported |
| MedicationRequest | Medication | Supported |
| AllergyIntolerance | Allergy | Planned |
| Procedure | Procedure | Planned |
| CarePlan | CarePlan | Planned |

## Ingestion Flow

1. Receive FHIR Bundle (transaction or batch)
2. Parse each entry's resource
3. Map FHIR fields → entity properties
4. Run entity resolution to prevent duplicates
5. Create/update entities in temporal KG
6. Stream numeric observations to TimescaleDB
7. Embed entities into Qdrant
