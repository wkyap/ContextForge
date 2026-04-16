"""Context compressor — LLM-based compression to fit token budgets."""

from __future__ import annotations

import logging

import litellm
import tiktoken

logger = logging.getLogger(__name__)

_COMPRESS_PROMPT = """Compress the following context while preserving all factual information
relevant to answering the user's question. Remove redundancy and filler.
Keep specific values, dates, names, and measurements intact.

User question: {question}

Context to compress:
{context}

Compressed context:"""


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


async def compress_context(
    context: str,
    question: str,
    *,
    max_tokens: int = 4000,
    model: str = "openai/gpt-4o-mini",
) -> str:
    """Compress context if it exceeds the token budget."""
    current_tokens = count_tokens(context)
    if current_tokens <= max_tokens:
        return context

    logger.info(
        "Compressing context: %d tokens → target %d", current_tokens, max_tokens
    )

    response = await litellm.acompletion(
        model=model,
        messages=[
            {
                "role": "user",
                "content": _COMPRESS_PROMPT.format(question=question, context=context),
            }
        ],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    compressed = response.choices[0].message.content or context
    new_tokens = count_tokens(compressed)
    logger.info("Compressed: %d → %d tokens (%.0f%% reduction)",
                current_tokens, new_tokens,
                (1 - new_tokens / current_tokens) * 100)
    return compressed
