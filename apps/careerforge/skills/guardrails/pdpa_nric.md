---
name: pdpa_nric
type: guardrail
domain: workforce
version: 1
description: "PDPA PII masking — NRIC, phone, email patterns for Singapore compliance"
author: human
tags: [guardrail, pdpa, pii, nric, singapore, compliance]
severity: block
patterns:
  - name: sg_nric
    regex: "[STFGM]\\d{7}[A-Z]"
    action: mask
    mask_format: "****{last4}"
  - name: sg_fin
    regex: "[FG]\\d{7}[A-Z]"
    action: mask
    mask_format: "****{last4}"
  - name: sg_phone
    regex: "[689]\\d{7}"
    action: mask
    mask_format: "****{last4}"
  - name: email_address
    regex: "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"
    action: mask_in_reports
  - name: credit_card
    regex: "\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}"
    action: block
---

# PDPA PII Guardrail

Enforces Singapore Personal Data Protection Act (PDPA) compliance.

## Rules

1. **NRIC/FIN**: Never include in AI prompts or outputs. SHA-256 hash for storage.
2. **Phone numbers**: Mask to last 4 digits in all displays and outputs.
3. **Email**: Full storage (needed for notifications), masked in compliance reports.
4. **Credit cards**: Block entirely — should never appear in this system.
5. **Addresses**: Not collected — not needed for programme management.

## Feb 2026 PDPC Directive

- Organizations must not collect, use, or disclose NRIC numbers unless required by law
- CareerForge does NOT require NRIC for any function — hash only for deduplication
- Display format: `S****567A` (first letter + last 4 characters only)

## Agent Notes

- This guardrail runs on EVERY AI output before it reaches the user
- If PII is detected in an AI response, mask it and log the incident
- Severity: BLOCK — PII leaks are compliance violations, not warnings
