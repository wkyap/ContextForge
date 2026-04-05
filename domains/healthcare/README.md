# Healthcare Domain Adapter

Primary demonstration domain for ContextForge.

## Directory Structure

| Folder | Purpose |
|--------|---------|
| `schema/` | Knowledge SKILL.md files — Patient, Encounter, Condition, Medication, Observation, Procedure, Allergy, CarePlan |
| `ingestion/` | Ingestion SKILL.md files — FHIR R4, HL7v2, CSV lab imports |
| `tools/` | Computation SKILL.md files — NEWS2, qSOFA, drug interactions, lab trend analysis |
| `templates/` | Template SKILL.md files — clinical summaries, handover notes, discharge letters |
| `guardrails/` | Guardrail SKILL.md files — PHI/PII detection, clinical safety checks |
| `channels/` | Channel SKILL.md files — WhatsApp, Teams, Slack adapters for clinical alerts |

## Key Entity Types

- **Patient** — demographics, identifiers (MRN, NHS number)
- **Encounter** — admissions, ED visits, outpatient appointments
- **Condition** — diagnoses (ICD-10/SNOMED coded)
- **Medication** — prescriptions, administrations (dm+d / RxNorm)
- **Observation** — vitals, lab results, clinical notes
- **Procedure** — surgical / diagnostic procedures (OPCS-4 / CPT)

## Data Sources

- FHIR R4 bundles (primary)
- Synthetic patient generator (for development)
- HL7v2 ADT/ORU feeds (planned)
