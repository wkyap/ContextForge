"""Guardrails orchestration layer — aggregate all safety checks into a single pass."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .hallucination_checker import check_hallucination
from .pii_detector import detect_pii
from .provenance import ProvenanceRecord
from .toxicity import check_toxicity

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """Aggregated result from all guardrail checks."""

    passed: bool = True
    pii_found: bool = False
    hallucination_found: bool = False
    toxicity_found: bool = False
    provenance_valid: bool = True
    domain_issues: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return not self.passed


class GuardrailsLayer:
    """Orchestrator that runs all guardrail checks and decides a routing action.

    Parameters
    ----------
    domain:
        Domain identifier (e.g. ``"healthcare"``, ``"finance"``).  Used to
        select domain-specific guardrail rules loaded from SKILL.md files of
        type ``"guardrail"``.
    """

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._domain_guardrails: list[dict[str, Any]] = []
        logger.info("GuardrailsLayer initialised for domain=%s", domain)

    # ------------------------------------------------------------------
    # Domain-specific guardrails
    # ------------------------------------------------------------------

    def register_domain_guardrail(self, guardrail: dict[str, Any]) -> None:
        """Register an additional domain-specific guardrail rule.

        Each *guardrail* dict should contain at minimum:

        * ``name``  — short identifier
        * ``pattern`` — regex string to match against output text
        * ``action``  — one of ``"block"`` or ``"rewrite"``
        * ``message`` — human-readable explanation
        """
        self._domain_guardrails.append(guardrail)
        logger.debug("Registered domain guardrail: %s", guardrail.get("name"))

    def load_domain_guardrails(self, skill_entries: list[dict[str, Any]]) -> None:
        """Load guardrails from parsed SKILL.md entries of type ``'guardrail'``.

        Parameters
        ----------
        skill_entries:
            List of dicts parsed from SKILL.md, each expected to have
            ``type == "guardrail"`` plus the keys required by
            :meth:`register_domain_guardrail`.
        """
        for entry in skill_entries:
            if entry.get("type") == "guardrail":
                self.register_domain_guardrail(entry)

    # ------------------------------------------------------------------
    # Core validation
    # ------------------------------------------------------------------

    async def validate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run every guardrail check against *state* and return aggregated results.

        *state* is expected to carry:

        * ``output``   — the generated text to validate
        * ``context``  — (optional) source context used for hallucination check
        * ``model``    — (optional) model used for hallucination check
        * ``provenance`` — (optional) a :class:`ProvenanceRecord` instance
        """
        output_text: str = state.get("output", "")
        context_text: str = state.get("context", "")
        model: str = state.get("model", "openai/gpt-4o-mini")
        provenance: ProvenanceRecord | None = state.get("provenance")

        result = GuardrailResult()

        # 1. PII detection -------------------------------------------------
        pii = detect_pii(output_text)
        result.pii_found = pii.found
        result.details["pii"] = {
            "found": pii.found,
            "count": len(pii.detections),
            "detections": pii.detections,
        }
        if pii.found:
            result.passed = False
            logger.warning("Guardrail: PII detected (%d instances)", len(pii.detections))

        # 2. Toxicity check ------------------------------------------------
        toxicity = await check_toxicity(output_text)
        result.toxicity_found = not toxicity.passed
        result.details["toxicity"] = {
            "passed": toxicity.passed,
            "score": toxicity.score,
            "details": toxicity.details,
        }
        if not toxicity.passed:
            result.passed = False
            logger.warning("Guardrail: toxicity flagged (score=%.2f)", toxicity.score)

        # 3. Hallucination check -------------------------------------------
        if context_text:
            hallucination = await check_hallucination(
                response=output_text,
                context=context_text,
                model=model,
            )
            result.hallucination_found = not hallucination.passed
            result.details["hallucination"] = {
                "passed": hallucination.passed,
                "unsupported_claims": hallucination.unsupported_claims,
                "confidence": hallucination.confidence,
            }
            if not hallucination.passed:
                result.passed = False
                logger.warning(
                    "Guardrail: %d unsupported claim(s)",
                    len(hallucination.unsupported_claims),
                )
        else:
            result.details["hallucination"] = {"skipped": True, "reason": "no context provided"}

        # 4. Provenance check ----------------------------------------------
        if provenance is not None:
            result.provenance_valid = provenance.has_sources
            result.details["provenance"] = provenance.to_dict()
            if not provenance.has_sources:
                result.passed = False
                logger.warning("Guardrail: response has no source attribution")
        else:
            result.details["provenance"] = {"skipped": True, "reason": "no provenance record"}

        # 5. Domain-specific guardrails ------------------------------------
        import re as _re

        for rule in self._domain_guardrails:
            pattern_str = rule.get("pattern", "")
            if not pattern_str:
                continue
            try:
                if _re.search(pattern_str, output_text, _re.IGNORECASE):
                    result.domain_issues.append(rule.get("message", rule.get("name", "domain rule")))
                    result.passed = False
                    logger.warning("Guardrail: domain rule '%s' triggered", rule.get("name"))
            except _re.error:
                logger.error("Invalid regex in domain guardrail '%s'", rule.get("name"))

        result.details["domain"] = {
            "domain": self.domain,
            "rules_checked": len(self._domain_guardrails),
            "issues": result.domain_issues,
        }

        return {
            "passed": result.passed,
            "pii_found": result.pii_found,
            "hallucination_found": result.hallucination_found,
            "toxicity_found": result.toxicity_found,
            "provenance_valid": result.provenance_valid,
            "domain_issues": result.domain_issues,
            "details": result.details,
        }

    # ------------------------------------------------------------------
    # Routing decision
    # ------------------------------------------------------------------

    async def route(self, state: dict[str, Any]) -> str:
        """Return a routing decision based on guardrail validation.

        Returns
        -------
        str
            One of:

            * ``"pass"``    — output is safe to deliver
            * ``"block"``   — output must be suppressed entirely
            * ``"rewrite"`` — output should be rewritten before delivery
        """
        results = await self.validate_output(state)

        if results["passed"]:
            return "pass"

        # Hard-block on toxicity or dangerous domain violations.
        if results["toxicity_found"]:
            return "block"

        # PII can often be redacted, so suggest a rewrite.
        if results["pii_found"] and not results["toxicity_found"]:
            return "rewrite"

        # Hallucinations and missing provenance warrant a rewrite.
        if results["hallucination_found"] or not results["provenance_valid"]:
            return "rewrite"

        # Domain issues default to block unless they are the only problem.
        if results["domain_issues"]:
            return "block"

        # Fallback — if something failed but we can't categorise it, block.
        return "block"
