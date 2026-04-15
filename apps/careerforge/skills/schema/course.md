---
name: course
type: knowledge
domain: workforce
version: 1
description: "Training course — SCTP, Place-and-Train, or employer-led programme offering"
author: human
tags: [entity, course, training, core]
entity_type: Course
properties:
  - name: course_id
    type: string
    required: true
  - name: title
    type: string
    required: true
  - name: provider
    type: string
    default: "NTUC LearningHub"
  - name: sector
    type: string
    enum: [ICT, Accounting, Tourism, Retail, Professional]
  - name: duration_weeks
    type: integer
  - name: mode
    type: string
    enum: [full-time, part-time, online, blended]
  - name: skills_taught
    type: list
    description: "SSG Skills Framework codes taught"
  - name: prerequisites
    type: list
  - name: ssg_course_code
    type: string
  - name: capacity
    type: integer
  - name: current_enrolment
    type: integer
    default: 0
  - name: intake_dates
    type: list
    description: "Upcoming intake dates"
relationships:
  - type: TEACHES
    target: Skill
    properties: [depth]
    description: "Skills taught at intro/intermediate/advanced level"
  - type: REQUIRES_PREREQ
    target: Skill
    description: "Prerequisite skills for enrolment"
  - type: PART_OF
    target: Programme
---

# Course Entity

Training courses offered through NTUC LearningHub career placement programmes.

## Agent Notes

- Match trainee's career goals to course outcomes, not just current skills
- Consider intake dates and capacity when recommending
- Flag when trainee lacks prerequisites — suggest bridging courses
- Duration matters: full-time courses suit unemployed transitioners; part-time for employed upskilling
- SSG course codes are critical for compliance reporting
