# SKILL.md Development Guide

## What is a Skill?

A skill is a markdown file with YAML frontmatter that teaches ContextForge about a domain concept, data source, computation, output format, safety rule, or messaging channel. Skills are the primary interface between domain experts and the engine.

## Skill Types

| Type | Purpose | Example |
|------|---------|---------|
| `knowledge` | Define an entity type and its properties | Patient, Asset, Compound |
| `ingestion` | Describe how to ingest data from a source | FHIR R4, MQTT, CSV |
| `computation` | Define a domain-specific calculation or tool | NEWS2 score, VaR, anomaly detection |
| `template` | Define an output format or report structure | Clinical summary, maintenance report |
| `guardrail` | Define a safety or compliance rule | PHI detection, threshold validation |
| `channel` | Configure a messaging channel | WhatsApp alerts, Slack notifications |

## File Structure

```markdown
---
name: patient
type: knowledge
domain: healthcare
version: 1
description: "Core patient entity with demographics and identifiers"
author: human
tags: [entity, demographics, identifiers]

# Type-specific fields vary by skill type (see below)
entity_type: Patient
properties:
  - name: mrn
    type: string
    required: true
    description: "Medical Record Number"
  - name: date_of_birth
    type: date
    required: true
relationships:
  - type: HAS_ENCOUNTER
    target: Encounter
    cardinality: one_to_many
---

# Patient

A patient represents an individual receiving or registered for healthcare services.

## Clinical Context

Patients are the root entity in the healthcare knowledge graph. Every clinical
event (encounter, observation, medication) links back to a patient node.

## Identifier Systems

| System | Format | Example |
|--------|--------|---------|
| MRN | Alphanumeric | `MRN-001234` |
| NHS Number | 10-digit | `9434765919` |

## Notes for Agents

- Always resolve patient identity before creating new nodes
- Check for existing aliases using the entity resolution service
- Date of birth is required for all patient nodes
```

## Frontmatter Reference

### Common Fields (all types)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique skill identifier (lowercase, underscores) |
| `type` | enum | yes | `knowledge`, `ingestion`, `computation`, `template`, `guardrail`, `channel` |
| `domain` | string | yes | Domain this skill belongs to |
| `version` | integer | yes | Monotonically increasing version |
| `description` | string | yes | One-line description for search |
| `author` | string | no | `human` or `tool-forge-agent` |
| `tags` | list | no | Searchable tags |

### Knowledge-Specific Fields

| Field | Description |
|-------|-------------|
| `entity_type` | Neo4j node label (PascalCase) |
| `properties` | List of property definitions (name, type, required, description) |
| `relationships` | List of relationship definitions (type, target, cardinality) |
| `temporal` | Whether entities are temporally versioned (default: true) |

### Ingestion-Specific Fields

| Field | Description |
|-------|-------------|
| `source_type` | `stream`, `document`, `api`, `batch` |
| `format` | Data format (fhir_r4, mqtt, csv, pdf, etc.) |
| `mapping` | Field mapping from source to entity properties |
| `schedule` | Cron expression for batch ingestion |

### Computation-Specific Fields

| Field | Description |
|-------|-------------|
| `inputs` | Required input parameters |
| `outputs` | Output fields and types |
| `algorithm` | Description of the calculation logic |
| `references` | Clinical/academic references |

### Template-Specific Fields

| Field | Description |
|-------|-------------|
| `output_format` | `markdown`, `html`, `pdf`, `json` |
| `sections` | Ordered list of template sections |
| `required_context` | Entity types needed to render |

### Guardrail-Specific Fields

| Field | Description |
|-------|-------------|
| `check_type` | `pii`, `hallucination`, `safety`, `compliance` |
| `severity` | `block`, `warn`, `log` |
| `rules` | List of validation rules |

### Channel-Specific Fields

| Field | Description |
|-------|-------------|
| `platform` | `whatsapp`, `slack`, `teams`, `web` |
| `message_format` | Platform-specific formatting rules |
| `rate_limits` | Messages per minute/hour caps |

## Best Practices

1. **One entity per skill** — keep knowledge skills focused on a single entity type
2. **Rich descriptions** — the markdown body is used by agents for reasoning context
3. **Version carefully** — bump the version when changing properties or relationships
4. **Tag generously** — tags improve semantic search for skill discovery
5. **Include examples** — agents perform better with concrete examples in the body
6. **Reference standards** — cite coding systems (ICD-10, SNOMED, ISO, etc.) where applicable
