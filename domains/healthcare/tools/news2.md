---
name: news2_score
type: computation
domain: healthcare
version: 1
description: "NEWS2 (National Early Warning Score 2) — aggregate deterioration risk from vital signs"
author: human
tags: [computation, early-warning, vitals, deterioration, safety]
inputs:
  - name: respiratory_rate
    type: float
    unit: breaths/min
    required: true
  - name: spo2
    type: float
    unit: "%"
    required: true
  - name: on_supplemental_o2
    type: boolean
    required: true
  - name: systolic_bp
    type: float
    unit: mmHg
    required: true
  - name: heart_rate
    type: float
    unit: beats/min
    required: true
  - name: consciousness
    type: string
    description: "ACVPU scale: Alert, Confusion, Voice, Pain, Unresponsive"
    required: true
  - name: temperature
    type: float
    unit: Cel
    required: true
outputs:
  - name: total_score
    type: integer
    description: "NEWS2 aggregate score (0-20)"
  - name: risk_level
    type: string
    description: "low, low-medium, medium, high"
  - name: component_scores
    type: object
    description: "Individual parameter scores"
algorithm: "RCP NEWS2 scoring chart (2017 revision)"
references:
  - "Royal College of Physicians. National Early Warning Score (NEWS) 2. 2017."
---

# NEWS2 Score

The National Early Warning Score 2 is a standardised tool for assessing acute illness severity. It uses 7 physiological parameters to calculate an aggregate score.

## Scoring Table

| Parameter | 3 | 2 | 1 | 0 | 1 | 2 | 3 |
|-----------|---|---|---|---|---|---|---|
| RR | ≤8 | | 9-11 | 12-20 | | 21-24 | ≥25 |
| SpO2 Scale 1 | ≤91 | 92-93 | 94-95 | ≥96 | | | |
| SpO2 Scale 2 | ≤83 | 84-85 | 86-87 | 88-92/≥93 on air | 93-94 on O2 | 95-96 on O2 | ≥97 on O2 |
| Systolic BP | ≤90 | 91-100 | 101-110 | 111-219 | | | ≥220 |
| Heart Rate | ≤40 | | 41-50 | 51-90 | 91-110 | 111-130 | ≥131 |
| Consciousness | | | | Alert | | | CVPU |
| Temperature | ≤35.0 | | 35.1-36.0 | 36.1-38.0 | 38.1-39.0 | ≥39.1 | |

## Clinical Response

| Score | Risk | Response |
|-------|------|----------|
| 0-4 | Low | Routine monitoring |
| 3 in single param | Low-Medium | Urgent ward assessment |
| 5-6 | Medium | Urgent response |
| ≥7 | High | Emergency response |
