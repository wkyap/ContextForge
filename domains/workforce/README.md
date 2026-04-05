# CareerForge — Workforce Domain Adapter

Domain adapter for NTUC LearningHub career placement programme management.

## Entity Types

| Entity | Description |
|--------|------------|
| Trainee | Job seeker enrolled in career transition programme |
| Course | Training course (SCTP, Place-and-Train, employer-led) |
| Employer | Hiring partner company |
| Skill | Competency mapped to SSG Skills Framework |
| JobOpening | Employer vacancy with requirements |
| Placement | Verified employment outcome |
| Programme | Government-funded programme (SCTP, PnT, etc.) |

## Programmes Supported

- **SCTP** — SkillsFuture Career Transition Programme
- **Place-and-Train** — Employment-first training model
- **Employer-led** — Company-sponsored workforce initiatives

## Sectors

ICT, Accounting, Tourism, Retail, Professional Services

## Data Sources

- NTUC LHub CRM (REST API or Excel export)
- Trainee self-service portal (document uploads)
- Employer portal (job openings)
- SSG Skills Framework taxonomy

## Compliance

- PDPA (Personal Data Protection Act) — Singapore
- NRIC masking per Feb 2026 PDPC directive
- SSG/WSG/IMDA reporting requirements
