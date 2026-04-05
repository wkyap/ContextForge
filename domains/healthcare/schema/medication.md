---
name: medication
type: knowledge
domain: healthcare
version: 1
description: "Medication prescription and administration records"
author: human
tags: [entity, medication, prescription, drug, core]
entity_type: Medication
properties:
  - name: medication_id
    type: string
    required: true
  - name: code
    type: string
    required: true
    description: "dm+d or RxNorm code"
  - name: display
    type: string
    required: true
    description: "Drug name"
  - name: status
    type: string
    required: true
    description: "active, completed, stopped, on-hold, cancelled"
  - name: dose
    type: string
    required: false
    description: "Dose value and unit (e.g., 500mg)"
  - name: route
    type: string
    required: false
    description: "Administration route (oral, IV, subcutaneous)"
  - name: frequency
    type: string
    required: false
    description: "Dosing frequency (e.g., twice daily, PRN)"
  - name: start_date
    type: datetime
    required: true
  - name: end_date
    type: datetime
    required: false
  - name: prescriber
    type: string
    required: false
relationships:
  - type: PRESCRIBED_FOR
    target: Patient
    cardinality: many_to_one
  - type: TREATS
    target: Condition
    cardinality: many_to_many
temporal: true
---

# Medication

Medications represent drug prescriptions and administrations. They link to conditions they treat and patients they're prescribed for.

## Agent Notes

- Always check for drug interactions when presenting multiple medications
- Flag if a patient has an allergy to a prescribed medication class
- Active medications with no end_date are considered ongoing
