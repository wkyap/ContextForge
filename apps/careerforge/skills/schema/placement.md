---
name: placement
type: knowledge
domain: workforce
version: 1
description: "Verified employment outcome — trainee placed at employer post-training"
author: human
tags: [entity, placement, outcome, compliance]
entity_type: Placement
properties:
  - name: placement_id
    type: string
    required: true
  - name: placement_type
    type: string
    enum: [full-time, part-time, contract]
  - name: source
    type: string
    enum: [lhub-matched, self-sourced]
  - name: start_date
    type: date
  - name: salary
    type: float
  - name: cpf_verified
    type: boolean
    default: false
  - name: status
    type: string
    enum: [pending, verified, rejected]
    default: pending
  - name: verified_date
    type: datetime
relationships:
  - type: FOR_TRAINEE
    target: Trainee
  - type: AT_EMPLOYER
    target: Employer
  - type: VIA_PROGRAMME
    target: Programme
---

# Placement Entity

Represents a verified employment outcome after training completion.

## Agent Notes

- Placements require document verification (payslip, CPF statement, or employment letter)
- SSG reporting distinguishes: full-time, part-time, self-sourced, LHub-matched
- CPF verification is the gold standard for employment proof in Singapore
- Salary data is sensitive — never include in AI prompts, only in aggregate reports
- Placement within 6 months of completion counts for programme KPIs
