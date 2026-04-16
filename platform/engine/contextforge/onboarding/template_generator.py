"""Template Generator — generate agent template SKILL.md files for domain use cases."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_TEMPLATE_PROMPT = """You are an AI agent template designer for the ContextForge platform.
Given a domain, its schema, and available tools, generate agent templates for common use cases.

Each template defines a system prompt and a set of tools an agent should use for a specific role.

Domain: {domain}

Schema entities:
{schema}

Available tools:
{tools}

Generate templates for different user roles and use cases (e.g. analyst, operator, auditor).

Return JSON:
{{
  "templates": [
    {{
      "name": "template_name",
      "description": "what this agent template is for",
      "role": "the user role this serves",
      "use_cases": ["use case 1", "use case 2"],
      "system_prompt": "the full system prompt for this agent template",
      "tool_set": ["tool_name_1", "tool_name_2"],
      "guardrails": ["guardrail references if applicable"],
      "skill_md": "full SKILL.md content with YAML frontmatter"
    }}
  ]
}}"""


class TemplateGenerator:
    """Generate agent template SKILL.md files from schema and tool analysis."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def generate(
        self,
        domain: str,
        schema: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate agent template SKILL.md proposals.

        Args:
            domain: Domain name.
            schema: Schema definitions from SchemaGenerator.
            tools: Tool definitions from ToolGenerator.

        Returns:
            List of template definition dicts with SKILL.md content.
        """
        schema_text = "\n".join(
            f"- {s.get('name', 'unnamed')}: {s.get('description', '')}"
            for s in schema[:15]
        )
        tools_text = "\n".join(
            f"- {t.get('name', 'unnamed')}: {t.get('description', '')}"
            for t in tools[:20]
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _TEMPLATE_PROMPT.format(
                    domain=domain,
                    schema=schema_text or "(no schema)",
                    tools=tools_text or "(no tools)",
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse template generation response")
            return []

        templates: list[dict[str, Any]] = data.get("templates", [])

        logger.info(
            "Generated %d agent templates for domain '%s'",
            len(templates),
            domain,
        )
        return templates
