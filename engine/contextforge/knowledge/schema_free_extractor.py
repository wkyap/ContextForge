"""Schema-free entity extraction — LLM-based extraction without predefined schema.

Used for 10% of ingestion to discover new entity types and relationships
that aren't yet defined in SKILL.md files.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """You are an entity extraction system. Given the following text,
extract all entities and relationships you can find.

Return a JSON object with this structure:
{
  "entities": [
    {"name": "...", "type": "...", "properties": {...}, "confidence": 0.0-1.0}
  ],
  "relationships": [
    {"from": "entity_name", "to": "entity_name", "type": "RELATIONSHIP_TYPE", "properties": {...}, "confidence": 0.0-1.0}
  ]
}

Rules:
- Entity types should be PascalCase (e.g., Patient, Medication, Asset)
- Relationship types should be UPPER_SNAKE_CASE (e.g., HAS_CONDITION, PRESCRIBED_BY)
- Include confidence scores based on how certain you are about each extraction
- Extract properties as key-value pairs where applicable
- Only extract factual information explicitly stated in the text

Text:
{text}"""


class SchemaFreeExtractor:
    """Extract entities and relationships from text without a predefined schema."""

    def __init__(self, *, model: str = "openai/gpt-4o-mini") -> None:
        self._model = model

    async def extract(self, text: str) -> dict[str, Any]:
        """Extract entities and relationships from free text."""
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": "You extract structured entities from text. Always respond with valid JSON."},
                {"role": "user", "content": _EXTRACTION_PROMPT.format(text=text)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Schema-free extraction returned invalid JSON")
            result = {"entities": [], "relationships": []}

        entities = result.get("entities", [])
        relationships = result.get("relationships", [])
        logger.info(
            "Schema-free extraction: %d entities, %d relationships",
            len(entities),
            len(relationships),
        )
        return result

    async def extract_batch(
        self, texts: list[str], *, sample_rate: float = 0.1
    ) -> list[dict[str, Any]]:
        """Extract from a sample of texts (default 10%)."""
        import random

        sample_size = max(1, int(len(texts) * sample_rate))
        sampled = random.sample(texts, min(sample_size, len(texts)))

        results = []
        for text in sampled:
            result = await self.extract(text)
            results.append(result)
        return results
