---
name: job_opening
type: knowledge
domain: workforce
version: 1
description: "Employer job vacancy — open position for trainee placement matching"
author: human
tags: [entity, job, vacancy, matching]
entity_type: JobOpening
properties:
  - name: opening_id
    type: string
    required: true
  - name: role_title
    type: string
    required: true
  - name: description
    type: string
  - name: required_skills
    type: list
  - name: preferred_skills
    type: list
  - name: experience_years
    type: integer
    default: 0
  - name: salary_min
    type: float
  - name: salary_max
    type: float
  - name: work_arrangement
    type: string
    enum: [onsite, hybrid, remote]
  - name: status
    type: string
    enum: [open, filled, closed]
    default: open
relationships:
  - type: REQUIRES
    target: Skill
    properties: [importance]
  - type: POSTED_BY
    target: Employer
---

# Job Opening Entity

Open positions posted by employer partners for trainee placement matching.

## Agent Notes

- Match composite scoring: technical skills 40%, experience 25%, qualifications 20%, practical 15%
- Distinguish required vs preferred skills — required skills are blockers, preferred are boosters
- Work arrangement matters: remote roles expand candidate pool geographically
- Salary range is used for expectation matching, not shared with trainees directly
