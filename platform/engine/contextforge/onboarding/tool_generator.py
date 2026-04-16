"""Tool Generator — propose computation and action SKILL.md files from schema."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_TOOL_PROMPT = """You are a tool design expert for the ContextForge platform. Given a domain,
its graph schema, and competency questions, propose computation and action tools.

Domain: {domain}

Schema entities:
{schema}

Competency questions to support:
{questions}

For each tool, generate a SKILL.md file. Tools should cover:
- Data retrieval and querying (e.g. "get_patient_history")
- Aggregation and analytics (e.g. "calculate_risk_score")
- Actions and mutations (e.g. "create_referral")
- Cross-entity computations (e.g. "find_related_cases")
- Temporal analysis (e.g. "trend_analysis")

Return JSON:
{{
  "tools": [
    {{
      "name": "tool_name",
      "description": "what the tool does",
      "category": "query | computation | action | analysis",
      "inputs": [
        {{"name": "param_name", "type": "string | int | list[str] | ...",
          "required": true, "description": "..."}}
      ],
      "outputs": [
        {{"name": "output_name", "type": "...", "description": "..."}}
      ],
      "implementation_notes": "key algorithms or APIs to use",
      "skill_md": "full SKILL.md content with YAML frontmatter"
    }}
  ]
}}"""


class ToolGenerator:
    """Generate computation and action tool proposals from schema analysis."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def generate(
        self,
        domain: str,
        schema: list[dict[str, Any]],
        questions: list[Any],
    ) -> list[dict[str, Any]]:
        """Generate tool SKILL.md proposals.

        Args:
            domain: Domain name.
            schema: Schema definitions from SchemaGenerator.
            questions: Competency questions to support.

        Returns:
            List of tool definition dicts with SKILL.md content.
        """
        schema_text = "\n".join(
            f"- {s.get('name', 'unnamed')}: {s.get('description', '')}"
            for s in schema[:20]
        )
        questions_text = "\n".join(
            f"- {getattr(q, 'question', str(q))}" for q in questions[:15]
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _TOOL_PROMPT.format(
                    domain=domain,
                    schema=schema_text or "(no schema)",
                    questions=questions_text or "(no questions)",
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse tool generation response")
            return []

        tools: list[dict[str, Any]] = data.get("tools", [])

        logger.info(
            "Generated %d tool proposals for domain '%s'",
            len(tools),
            domain,
        )
        return tools
