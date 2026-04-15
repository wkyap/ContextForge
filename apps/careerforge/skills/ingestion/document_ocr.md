---
name: document_ocr
type: ingestion
domain: workforce
version: 1
description: "Document OCR extraction — payslips, CPF statements, employment letters"
author: human
tags: [ingestion, ocr, document, verification]
supported_types:
  - payslip
  - cpf_statement
  - employment_letter
  - certificate
---

# Document OCR Pipeline

Extracts structured data from uploaded employment verification documents.

## Extraction Templates

### Payslip
- Employer name
- Employee name
- Pay period (month/year)
- Basic salary
- CPF contribution (employee + employer)
- Net pay

### CPF Statement
- Member name (match to trainee)
- Employer name
- Contribution period
- Ordinary account contribution
- Employment start date (inferred)

### Employment Letter
- Company letterhead / name
- Employee name
- Position / role title
- Employment start date
- Employment type (full-time/part-time/contract)
- Salary (if stated)

## Confidence Scoring

- >95%: All key fields extracted, cross-references match → auto-approve eligible
- 70-95%: Most fields extracted, minor mismatches → flag for human review
- <70%: Significant extraction failures or mismatches → reject with reason

## Agent Notes

- Vision LLM (GPT-4V) for complex or handwritten documents
- Tesseract OCR for clean printed documents (faster, cheaper)
- Always cross-reference extracted employer name against KG employer entities
- Validate CPF contribution amounts against salary (should be ~37% combined)
