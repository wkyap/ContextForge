"""Model router — select the right LLM tier for each task."""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class ModelTier(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# Default model mapping (LiteLLM model names).
# ~70% small/local, ~25% medium, ~5% large.
TASK_MODEL_MAP: dict[str, str] = {
    # ── Small / Local (fast, cheap or free) ────────────────────────────
    "context_compression": "litellm:anthropic/claude-haiku-4-5",
    "entity_resolution": "litellm:ollama/phi4-mini",
    "query_classification": "litellm:ollama/phi4-mini",
    "guardrails_validation": "litellm:anthropic/claude-haiku-4-5",
    "extraction": "litellm:anthropic/claude-haiku-4-5",
    "embedding": "openai/text-embedding-3-small",
    "summarization": "litellm:anthropic/claude-haiku-4-5",
    "validation": "litellm:anthropic/claude-haiku-4-5",

    # ── Medium (balanced) ──────────────────────────────────────────────
    "orchestrator_planning": "litellm:anthropic/claude-sonnet-4-6",
    "retrieval_synthesis": "litellm:anthropic/claude-sonnet-4-6",
    "action_recommendation": "litellm:anthropic/claude-sonnet-4-6",
    "chat": "litellm:anthropic/claude-sonnet-4-6",
    "tool_selection": "litellm:anthropic/claude-sonnet-4-6",
    "entity_extraction": "litellm:anthropic/claude-sonnet-4-6",

    # ── Large (complex reasoning — sparingly) ─────────────────────────
    "complex_analysis": "litellm:anthropic/claude-opus-4-6",
    "root_cause_reasoning": "litellm:anthropic/claude-opus-4-6",
    "schema_evolution": "litellm:anthropic/claude-opus-4-6",
    "tool_generation": "litellm:anthropic/claude-opus-4-6",
}

TIER_MODELS: dict[ModelTier, str] = {
    ModelTier.SMALL: "litellm:anthropic/claude-haiku-4-5",
    ModelTier.MEDIUM: "litellm:anthropic/claude-sonnet-4-6",
    ModelTier.LARGE: "litellm:anthropic/claude-opus-4-6",
}


def get_model_for_task(task: str) -> str:
    """Look up the LiteLLM model name for a given task type."""
    model = TASK_MODEL_MAP.get(task)
    if model:
        return model
    logger.debug("No model mapping for task '%s', defaulting to medium", task)
    return TIER_MODELS[ModelTier.MEDIUM]


def get_model_for_tier(tier: ModelTier) -> str:
    """Get the model for a given tier."""
    return TIER_MODELS[tier]
