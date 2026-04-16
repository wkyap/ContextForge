---
name: excel_import
type: ingestion
domain: workforce
version: 1
description: "Excel tracking sheet import — parse NTUC LHub master Excel into KG entities"
author: human
tags: [ingestion, excel, import, data-migration]
source_format: xlsx
entity_mappings:
  - sheet: "Trainees"
    entity_type: Trainee
    id_column: "Trainee ID"
    field_map:
      name: "Full Name"
      email: "Email Address"
      education_level: "Education"
      years_experience: "Years Exp"
      programme_type: "Programme"
      status: "Status"
  - sheet: "Courses"
    entity_type: Course
    id_column: "Course Code"
    field_map:
      title: "Course Title"
      sector: "Sector"
      duration_weeks: "Duration (Weeks)"
      mode: "Mode"
      ssg_course_code: "SSG Code"
  - sheet: "Employers"
    entity_type: Employer
    id_column: "UEN"
    field_map:
      company_name: "Company Name"
      sector: "Industry"
      size: "Company Size"
      contact_email: "Contact Email"
---

# Excel Import

Parses NTUC LHub's master tracking Excel spreadsheets into structured entities.

## Agent Notes

- Excel is the current source of truth — handle messy data gracefully
- Column names may vary between sheets — use fuzzy matching
- NRIC column: hash immediately, never store raw
- Phone column: mask to last 4 digits on import
- Duplicate detection: match on trainee_id or email
