"""AI-Native Domain Onboarding Wizard — guide users through adding a new domain."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_WIZARD_PROMPT = """You are helping a user onboard a new domain to the ContextForge platform.
Based on their description, generate the initial SKILL.md files needed.

Domain name: {domain_name}
Domain description: {description}
Example entities: {entities}

Generate a JSON response with:
{{
  "domain_name": "...",
  "entity_types": [
    {{
      "name": "entity_name",
      "type": "PascalCase",
      "properties": [{{"name": "...", "type": "...", "required": true/false}}],
      "relationships": [{{"type": "REL_TYPE", "target": "OtherEntity"}}],
      "skill_md": "full SKILL.md content"
    }}
  ],
  "ingestion_skills": [
    {{
      "name": "source_name",
      "source_type": "api|stream|document|batch",
      "skill_md": "full SKILL.md content"
    }}
  ],
  "suggested_tools": ["tool description 1", "..."],
  "suggested_guardrails": ["guardrail description 1", "..."]
}}"""


class DomainOnboardingWizard:
    """Guide the creation of a new domain adapter."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def generate_domain_plan(
        self,
        *,
        domain_name: str,
        description: str,
        example_entities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a domain onboarding plan with initial SKILL.md files."""
        entities_str = ", ".join(example_entities) if example_entities else "not specified"

        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _WIZARD_PROMPT.format(
                    domain_name=domain_name,
                    description=description,
                    entities=entities_str,
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            plan = {"error": "Failed to generate plan"}

        logger.info(
            "Domain onboarding plan for '%s': %d entity types, %d ingestion skills",
            domain_name,
            len(plan.get("entity_types", [])),
            len(plan.get("ingestion_skills", [])),
        )
        return plan

    async def validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Validate a generated plan for completeness."""
        issues: list[str] = []

        if not plan.get("entity_types"):
            issues.append("No entity types defined")
        for et in plan.get("entity_types", []):
            if not et.get("properties"):
                issues.append(f"Entity '{et.get('name')}' has no properties")

        if not plan.get("ingestion_skills"):
            issues.append("No ingestion skills defined — how will data enter the system?")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "entity_count": len(plan.get("entity_types", [])),
            "ingestion_count": len(plan.get("ingestion_skills", [])),
        }
