"""Schema Generator — propose graph schema from domain docs and competency questions."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_SCHEMA_PROMPT = """You are a knowledge graph schema architect. Given a domain, competency questions,
and sample documents, propose a graph schema with entity types, relationship types, and properties.

Domain: {domain}

Competency questions:
{questions}

Document excerpts:
{documents}

Align with known standards when applicable:
- Healthcare: FHIR R4, HL7, SNOMED CT
- Manufacturing: ISA-95, OPC-UA
- Finance: FIBO, FpML
- Legal: LKIF, Akoma Ntoso

Return JSON:
{{
  "schemas": [
    {{
      "name": "EntityTypeName",
      "type": "entity | relationship",
      "description": "what this represents",
      "properties": [
        {{
          "name": "property_name",
          "type": "string | int | float | boolean | datetime | json",
          "required": true,
          "description": "..."
        }}
      ],
      "relationships": [
        {{
          "type": "REL_TYPE",
          "target": "OtherEntityType",
          "cardinality": "one_to_one | one_to_many | many_to_many"
        }}
      ],
      "standard_alignment": "FHIR.Patient | ISA-95.Equipment | null",
      "skill_md": "full SKILL.md content with YAML frontmatter for this knowledge schema"
    }}
  ],
  "detected_standards": ["FHIR", "ISA-95"]
}}"""


class SchemaGenerator:
    """Generate graph schema proposals from domain analysis."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def generate(
        self,
        domain: str,
        questions: list[Any],
        documents: list[str],
    ) -> list[dict[str, Any]]:
        """Generate graph schema from domain analysis.

        Args:
            domain: Domain name (e.g. "healthcare", "manufacturing").
            questions: Competency questions from the question generator.
            documents: Sample document excerpts for context.

        Returns:
            List of schema definition dicts, each containing a SKILL.md.
        """
        questions_text = "\n".join(
            f"- {getattr(q, 'question', str(q))}" for q in questions[:20]
        )
        docs_text = "\n---\n".join(
            f"Document {i + 1}:\n{doc[:1500]}" for i, doc in enumerate(documents[:8])
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _SCHEMA_PROMPT.format(
                    domain=domain,
                    questions=questions_text or "(none)",
                    documents=docs_text or "(no documents provided)",
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse schema generation response")
            return []

        schemas = data.get("schemas", [])
        detected = data.get("detected_standards", [])

        if detected:
            logger.info(
                "Schema generator detected standards: %s",
                ", ".join(detected),
            )

        logger.info(
            "Generated %d schema definitions for domain '%s'",
            len(schemas),
            domain,
        )
        return schemas
