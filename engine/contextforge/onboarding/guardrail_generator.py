"""Guardrail Generator — propose domain-specific guardrail SKILL.md files."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_GUARDRAIL_PROMPT = """You are a compliance and safety expert for the ContextForge platform.
Given a domain and its schema, propose guardrail SKILL.md files that enforce safety,
compliance, and data governance rules.

Domain: {domain}

Schema entities:
{schema}

Detect and address applicable compliance frameworks:
- Healthcare: HIPAA, HITECH, FDA 21 CFR Part 11, GDPR (health data)
- Manufacturing: IEC 62443, ISO 27001, NIST SP 800-82
- Finance: SOX, PCI-DSS, MiFID II, GDPR
- General: GDPR, CCPA, SOC 2

For each guardrail, specify:
- What it checks (input validation, output filtering, access control, audit)
- When it triggers (pre-query, post-generation, on-write, periodic)
- Severity (block, warn, log)

Return JSON:
{{
  "guardrails": [
    {{
      "name": "guardrail_name",
      "description": "what this guardrail enforces",
      "compliance_framework": "HIPAA | IEC 62443 | GDPR | null",
      "check_type": "input_validation | output_filtering | access_control | audit_logging | data_retention",
      "trigger": "pre_query | post_generation | on_write | periodic",
      "severity": "block | warn | log",
      "rules": ["rule description 1", "rule description 2"],
      "skill_md": "full SKILL.md content with YAML frontmatter"
    }}
  ],
  "detected_frameworks": ["HIPAA", "GDPR"]
}}"""


class GuardrailGenerator:
    """Generate domain-specific guardrail SKILL.md proposals."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def generate(
        self,
        domain: str,
        schema: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate guardrail SKILL.md proposals.

        Args:
            domain: Domain name.
            schema: Schema definitions from SchemaGenerator.

        Returns:
            List of guardrail definition dicts with SKILL.md content.
        """
        schema_text = "\n".join(
            f"- {s.get('name', 'unnamed')}: {s.get('description', '')} "
            f"(properties: {', '.join(p.get('name', '') for p in s.get('properties', []))})"
            for s in schema[:15]
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _GUARDRAIL_PROMPT.format(
                    domain=domain,
                    schema=schema_text or "(no schema)",
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse guardrail generation response")
            return []

        guardrails: list[dict[str, Any]] = data.get("guardrails", [])
        detected = data.get("detected_frameworks", [])

        if detected:
            logger.info(
                "Guardrail generator detected compliance frameworks: %s",
                ", ".join(detected),
            )

        logger.info(
            "Generated %d guardrail proposals for domain '%s'",
            len(guardrails),
            domain,
        )
        return guardrails
