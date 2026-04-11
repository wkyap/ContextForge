"""Tool Forge Agent — generates new computation tools from requirements."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_FORGE_PROMPT = """You are a tool generation system. Given a description of a needed computation tool,
generate a SKILL.md file and a Python implementation.

Tool request: {request}
Domain: {domain}

Return JSON:
{{
  "skill_md": "full SKILL.md content with frontmatter",
  "python_code": "Python implementation of the computation",
  "name": "tool_name",
  "description": "what the tool does",
  "test_cases": [{{"inputs": {{}}, "expected_output": {{}}}}]
}}"""


class ToolForgeAgent:
    """Generate new computation tools from natural language descriptions."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def forge_tool(
        self, request: str, *, domain: str = "healthcare"
    ) -> dict[str, Any]:
        """Generate a new tool from a description."""
        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _FORGE_PROMPT.format(request=request, domain=domain),
            }],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            result = {"error": "Failed to generate tool"}

        logger.info("Tool forge: generated '%s'", result.get("name", "unknown"))
        return result
