"""Guardrails — safety checks applied to agent outputs before delivery.

Modules
-------
pii_detector
    Regex-based PII / PHI detection and automatic redaction.
hallucination_checker
    LLM-assisted verification of claims against retrieved source context.
provenance
    Source attribution tracking for agent responses.
toxicity
    Pattern-based detection of harmful medical advice, dangerous
    instructions, and discriminatory content.
layer
    Orchestration layer that aggregates all guardrail checks and returns
    a routing decision (pass / block / rewrite).
"""
