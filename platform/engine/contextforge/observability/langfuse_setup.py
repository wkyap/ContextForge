"""Langfuse observability — client init and LiteLLM callback wiring."""

from __future__ import annotations

import logging

import litellm
from langfuse import Langfuse

from contextforge.config import Settings

logger = logging.getLogger(__name__)

_langfuse: Langfuse | None = None


def init_langfuse(settings: Settings) -> Langfuse:
    """Initialise the Langfuse client and register the LiteLLM callback."""
    global _langfuse  # noqa: PLW0603

    _langfuse = Langfuse(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )

    # Wire Langfuse as a LiteLLM success/failure callback so every
    # LLM call is automatically traced.
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

    logger.info("Langfuse initialised (%s)", settings.langfuse_host)
    return _langfuse


def get_langfuse() -> Langfuse:
    """Return the singleton Langfuse client (must be initialised first)."""
    if _langfuse is None:
        raise RuntimeError("Langfuse not initialised — call init_langfuse() first")
    return _langfuse


def shutdown_langfuse() -> None:
    """Flush pending events and shut down."""
    global _langfuse  # noqa: PLW0603
    if _langfuse is not None:
        _langfuse.flush()
        _langfuse.shutdown()
        _langfuse = None
        logger.info("Langfuse shut down")
