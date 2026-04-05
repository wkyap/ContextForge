---
name: ssg_report_generator
type: tool
domain: workforce
version: 1
description: "SSG compliance report generator — monthly/quarterly reports in government-required format"
author: human
tags: [tool, compliance, ssg, reporting]
---

# SSG Report Generator

Generates compliance reports for SkillsFuture Singapore (SSG), Workforce Singapore (WSG), and IMDA.

## Report Fields (SSG Monthly)

- Programme name and code
- Reporting period
- Total enrolment count (by intake)
- Training completion rate
- Placement rate (within 6 months)
- Employment type breakdown (full-time, part-time, contract)
- Placement source (LHub-matched vs self-sourced)
- Salary range distribution
- Employer list (with UEN)
- At-risk trainee count and interventions

## Agent Notes

- Reports ALWAYS require human sign-off (autonomy level L1, never auto-promote)
- Placement rate = verified placements / completed trainees * 100
- Only include placements with verified documents (status = verified)
- CPF-verified placements have highest confidence
- Self-sourced placements still count for programme KPIs
