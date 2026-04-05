---
name: condition
type: knowledge
domain: healthcare
version: 1
description: "Clinical condition/diagnosis — ICD-10/SNOMED coded problems"
author: human
tags: [entity, condition, diagnosis, problem, core]
entity_type: Condition
properties:
  - name: condition_id
    type: string
    required: true
  - name: code
    type: string
    required: true
    description: "ICD-10 or SNOMED CT code"
  - name: code_system
    type: string
    required: true
    description: "Coding system (icd-10, snomed-ct)"
  - name: display
    type: string
    required: true
    description: "Human-readable condition name"
  - name: clinical_status
    type: string
    required: true
    description: "active, recurrence, relapse, inactive, remission, resolved"
  - name: verification_status
    type: string
    required: false
    description: "unconfirmed, provisional, differential, confirmed"
  - name: severity
    type: string
    required: false
    description: "mild, moderate, severe"
  - name: onset_date
    type: datetime
    required: false
  - name: abatement_date
    type: datetime
    required: false
  - name: recorded_date
    type: datetime
    required: true
relationships:
  - type: CONDITION_OF
    target: Patient
    cardinality: many_to_one
  - type: DIAGNOSED_DURING
    target: Encounter
    cardinality: many_to_one
temporal: true
---

# Condition

A condition represents a clinical diagnosis, problem, or health concern. Conditions form the clinical problem list and drive care planning.

## Agent Notes

- Active conditions with high severity should be highlighted in summaries
- Check for related medications when presenting conditions
- Use SNOMED CT codes for clinical specificity, ICD-10 for administrative purposes
