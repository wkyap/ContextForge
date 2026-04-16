---
name: skill
type: knowledge
domain: workforce
version: 1
description: "Competency mapped to SSG Skills Framework — technical, soft, or domain skill"
author: human
tags: [entity, skill, taxonomy, ssg]
entity_type: Skill
properties:
  - name: skill_id
    type: string
    required: true
  - name: name
    type: string
    required: true
  - name: category
    type: string
    enum: [technical, soft, domain]
  - name: ssg_framework_code
    type: string
    description: "SSG Skills Framework reference code"
  - name: proficiency_levels
    type: list
    description: "Defined proficiency levels 1-5"
  - name: demand_score
    type: float
    description: "Computed from job posting frequency"
relationships:
  - type: PARENT_OF
    target: Skill
    description: "SSG taxonomy hierarchy"
  - type: TRANSFERS_TO
    target: Skill
    description: "Cross-domain skill transferability"
---

# Skill Entity

Skills mapped to the SSG (SkillsFuture Singapore) Skills Framework taxonomy.

## Agent Notes

- TRANSFERS_TO relationships are critical for career transitioners
- Example: "Customer Service" (Retail) TRANSFERS_TO "Stakeholder Management" (Professional)
- Example: "Inventory Management" (Retail) TRANSFERS_TO "Data Analysis" (ICT)
- Proficiency levels: 1=Awareness, 2=Basic, 3=Intermediate, 4=Advanced, 5=Expert
- demand_score helps prioritize recommendations toward high-demand skills
