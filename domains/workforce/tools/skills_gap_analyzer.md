---
name: skills_gap_analyzer
type: tool
domain: workforce
version: 1
description: "Skills gap analysis — map trainee skills against target role/course requirements"
author: human
tags: [tool, skills, gap-analysis, recommendation]
---

# Skills Gap Analyzer

Identifies gaps between a trainee's current skill set and the requirements of a target role or course.

## Process

1. Extract trainee's skills from KG (HAS_SKILL relationships)
2. Extract target requirements (course TEACHES or job REQUIRES relationships)
3. For each required skill, check if trainee has it at sufficient proficiency
4. Identify transferable skills via TRANSFERS_TO relationships
5. Compute gap severity: critical (must-have missing) vs nice-to-have

## Agent Notes

- Transferable skills reduce gap severity — highlight these prominently
- Suggest specific courses that bridge identified gaps
- Career transitioners will always have gaps — focus on bridgeable ones
- Group gaps by category (technical, soft, domain) for clarity
