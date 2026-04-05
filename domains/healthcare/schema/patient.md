---
name: patient
type: knowledge
domain: healthcare
version: 1
description: "Core patient entity — demographics, identifiers, and contact information"
author: human
tags: [entity, demographics, identifiers, core]
entity_type: Patient
properties:
  - name: mrn
    type: string
    required: true
    description: "Medical Record Number — primary hospital identifier"
  - name: nhs_number
    type: string
    required: false
    description: "NHS Number (UK) — 10-digit national identifier"
  - name: given_name
    type: string
    required: true
    description: "Patient's given (first) name"
  - name: family_name
    type: string
    required: true
    description: "Patient's family (last) name"
  - name: date_of_birth
    type: date
    required: true
    description: "Date of birth (YYYY-MM-DD)"
  - name: gender
    type: string
    required: true
    description: "Administrative gender (male, female, other, unknown)"
  - name: deceased
    type: boolean
    required: false
    description: "Whether the patient is deceased"
  - name: address
    type: string
    required: false
    description: "Current address (free text)"
  - name: phone
    type: string
    required: false
    description: "Primary contact phone number"
  - name: email
    type: string
    required: false
    description: "Email address"
  - name: language
    type: string
    required: false
    description: "Preferred communication language (BCP-47)"
relationships:
  - type: HAS_ENCOUNTER
    target: Encounter
    cardinality: one_to_many
  - type: HAS_CONDITION
    target: Condition
    cardinality: one_to_many
  - type: HAS_MEDICATION
    target: Medication
    cardinality: one_to_many
  - type: HAS_ALLERGY
    target: Allergy
    cardinality: one_to_many
temporal: true
---

# Patient

A patient represents an individual who is receiving or is registered to receive healthcare services. Patients are the root entity in the healthcare knowledge graph — every clinical event links back to a patient.

## Identity Management

- **MRN** is the primary identifier within a hospital system
- **NHS Number** (UK) or equivalent national identifier provides cross-system linkage
- Always run entity resolution before creating a new Patient node to prevent duplicates
- Name matching should be fuzzy (handle spelling variations, maiden names)

## FHIR R4 Mapping

| FHIR Path | Property | Notes |
|-----------|----------|-------|
| `Patient.identifier[mrn]` | `mrn` | Use type = "MR" |
| `Patient.identifier[nhs]` | `nhs_number` | System = `https://fhir.nhs.uk/Id/nhs-number` |
| `Patient.name[0].given[0]` | `given_name` | First given name |
| `Patient.name[0].family` | `family_name` | |
| `Patient.birthDate` | `date_of_birth` | |
| `Patient.gender` | `gender` | |

## Agent Notes

- When asked "who is this patient?", compose a summary from Patient + latest Encounters + active Conditions
- Age is computed from `date_of_birth`, never stored separately
- Deceased patients should still be queryable for audit/research purposes
