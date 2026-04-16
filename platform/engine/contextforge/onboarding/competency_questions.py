"""Competency Question Generator — derive domain competency questions from documents."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import litellm

logger = logging.getLogger(__name__)

_CQ_PROMPT = """You are a domain ontology expert. Given the domain description and sample documents,
generate competency questions that the knowledge graph must be able to answer.

Domain description: {domain_description}

Sample document excerpts:
{sample_docs}

Return a JSON array of competency questions:
{{
  "questions": [
    {{
      "question": "What is the relationship between X and Y?",
      "expected_answer_type": "entity_list | scalar | boolean | aggregation | temporal",
      "data_sources_needed": ["source1", "source2"],
      "priority": "high | medium | low"
    }}
  ]
}}

Generate 10-20 questions covering:
- Core entity relationships
- Temporal queries (trends, changes over time)
- Aggregation queries (counts, averages, distributions)
- Compliance / governance queries
- Operational queries users would ask day-to-day"""


@dataclass
class CompetencyQuestion:
    """A single competency question for the domain."""

    question: str
    expected_answer_type: str
    data_sources_needed: list[str]
    priority: str  # high | medium | low


class CompetencyQuestionGenerator:
    """Generate competency questions from domain descriptions and sample documents."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def generate(
        self,
        domain_description: str,
        sample_docs: list[str],
    ) -> list[CompetencyQuestion]:
        """Generate competency questions from domain docs.

        Args:
            domain_description: Natural-language description of the domain.
            sample_docs: Excerpts from representative domain documents.

        Returns:
            Ordered list of competency questions by priority.
        """
        docs_text = "\n---\n".join(
            f"Document {i + 1}:\n{doc[:2000]}" for i, doc in enumerate(sample_docs[:10])
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{
                "role": "user",
                "content": _CQ_PROMPT.format(
                    domain_description=domain_description,
                    sample_docs=docs_text or "(no sample documents provided)",
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse competency questions response")
            return []

        questions = [
            CompetencyQuestion(
                question=q["question"],
                expected_answer_type=q.get("expected_answer_type", "entity_list"),
                data_sources_needed=q.get("data_sources_needed", []),
                priority=q.get("priority", "medium"),
            )
            for q in data.get("questions", [])
            if "question" in q
        ]

        # Sort by priority: high > medium > low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        questions.sort(key=lambda q: priority_order.get(q.priority, 1))

        logger.info(
            "Generated %d competency questions for domain",
            len(questions),
        )
        return questions
