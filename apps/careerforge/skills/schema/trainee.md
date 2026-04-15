---
name: trainee
type: knowledge
domain: workforce
version: 1
description: "Career transition trainee — job seeker enrolled in NTUC LHub placement programme"
author: human
tags: [entity, trainee, core, career-placement]
entity_type: Trainee
properties:
  - name: trainee_id
    type: string
    required: true
    description: "Unique trainee identifier"
  - name: name
    type: string
    required: true
  - name: email
    type: string
    required: true
  - name: phone_masked
    type: string
    description: "Last 4 digits only for PDPA compliance"
  - name: nric_hash
    type: string
    description: "SHA-256 hash — never store raw NRIC"
  - name: education_level
    type: string
    enum: [secondary, diploma, degree, masters, phd, professional_cert]
  - name: field_of_study
    type: string
  - name: years_experience
    type: integer
    default: 0
  - name: career_goals
    type: list
    description: "Target roles or sectors"
  - name: preferred_sectors
    type: list
    enum_values: [ICT, Accounting, Tourism, Retail, Professional]
  - name: preferred_locations
    type: list
  - name: programme_type
    type: string
    enum: [SCTP, Place-and-Train, employer-led]
  - name: status
    type: string
    enum: [applied, enrolled, training, completed, placed, inactive]
    default: applied
relationships:
  - type: HAS_SKILL
    target: Skill
    properties: [proficiency, source, verified_date]
  - type: ENROLLED_IN
    target: Course
    properties: [enrol_date, status, completion_date, match_score]
  - type: APPLIED_TO
    target: JobOpening
    properties: [apply_date, match_score, status]
  - type: PLACED_AT
    target: Employer
    properties: [placement_id, start_date, salary, verified]
  - type: IN_PROGRAMME
    target: Programme
  - type: SUBMITTED
    target: Document
pii_fields: [name, email, phone_masked, nric_hash]
---

# Trainee Entity

Represents a job seeker or career transitioner enrolled in an NTUC LearningHub career placement programme.

## Lifecycle States

```
applied → enrolled → training → completed → placed
                                    └──→ inactive (non-completion)
```

## Agent Notes

- Always mask NRIC before including in any AI prompt or output
- Phone numbers: store and display last 4 digits only
- Skills should be mapped to SSG Skills Framework codes where possible
- Transferable skills detection is critical for career transitioners (e.g., retail manager → business analyst)
- Career goals drive course recommendation — weight heavily in matching

## PDPA Compliance

- NRIC: SHA-256 hash only, never raw. Display as `****1234A`
- Phone: Last 4 digits. Display as `****5678`
- Email: Full email stored (needed for notifications), but masked in reports
- Address: Never collected (not needed for programme management)
