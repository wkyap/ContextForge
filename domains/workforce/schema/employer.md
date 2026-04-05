---
name: employer
type: knowledge
domain: workforce
version: 1
description: "Employer partner — hiring company in NTUC LHub placement network"
author: human
tags: [entity, employer, partner, core]
entity_type: Employer
properties:
  - name: employer_id
    type: string
    required: true
  - name: company_name
    type: string
    required: true
  - name: uen
    type: string
    description: "Singapore Unique Entity Number"
  - name: sector
    type: string
    enum: [ICT, Accounting, Tourism, Retail, Professional, Manufacturing, Healthcare, Finance, Logistics]
  - name: size
    type: string
    enum: [sme, mnc, gov, startup]
  - name: locations
    type: list
  - name: hiring_needs
    type: list
  - name: culture_keywords
    type: list
  - name: partnership_tier
    type: string
    enum: [new, active, preferred, strategic]
    default: new
  - name: contact_email
    type: string
relationships:
  - type: POSTED
    target: JobOpening
  - type: REQUIRES_SKILL
    target: Skill
    properties: [importance]
  - type: PARTNERS_WITH
    target: Programme
---

# Employer Entity

Companies partnered with NTUC LearningHub for trainee placement.

## Agent Notes

- Partnership tier affects match priority: strategic > preferred > active > new
- Past hiring patterns (from feedback loop) improve future match quality
- Location matching: consider trainee's preferred locations vs employer office locations
- SMEs may need more hand-holding; MNCs have structured onboarding
- Employer feedback on match quality feeds into matching algorithm improvement
