---
name: matching_scorer
type: tool
domain: workforce
version: 1
description: "Composite match scoring — trainee-to-job and trainee-to-course matching formula"
author: human
tags: [tool, matching, scoring, algorithm]
input_schema:
  trainee_skills: "list of {skill_id, proficiency}"
  target_requirements: "list of {skill_id, importance: must|nice}"
  trainee_experience_years: integer
  target_experience_years: integer
  trainee_education_level: string
  target_education_level: string
  location_match: boolean
output_schema:
  composite_score: float
  skill_coverage: float
  score_breakdown: object
  explanation: string
---

# Matching Scorer

Computes composite match scores between trainees and job openings or courses.

## Scoring Formula

```
composite_score = (
    skill_score     * 0.40 +
    experience_score * 0.25 +
    qualification_score * 0.20 +
    practical_score  * 0.15
)
```

### Skill Score (40%)
- Count required skills met / total required skills
- Add bonus for preferred skills met (0.1 per preferred skill, max 0.3)
- Weight by proficiency match (trainee proficiency >= required = full credit)

### Experience Score (25%)
- Exact or over target = 1.0
- Within 1 year = 0.8
- Within 2 years = 0.6
- 3+ years gap = 0.3
- Transferable experience counts at 70% weight

### Qualification Score (20%)
- Exact match = 1.0
- One level above = 1.0
- One level below = 0.6
- Two levels below = 0.3

### Practical Score (15%)
- Location match = 0.4 of practical score
- Availability alignment = 0.3
- Work arrangement preference match = 0.3

## Agent Notes

- Scores >= 80% = strong match (recommend)
- Scores 60-79% = moderate match (include with caveats)
- Scores < 60% = weak match (exclude unless no better options)
- Always explain gaps to coordinator — not just the score
