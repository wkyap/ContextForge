"""Skill validation — ensures frontmatter is well-formed per skill type."""

from __future__ import annotations

from dataclasses import dataclass, field

from contextforge.skills.loader import Skill

VALID_TYPES = {"knowledge", "ingestion", "computation", "template", "guardrail", "channel"}

# Required metadata keys per skill type (beyond the common fields).
_TYPE_REQUIRED: dict[str, list[str]] = {
    "knowledge": ["entity_type", "properties"],
    "ingestion": ["source_type", "format"],
    "computation": ["inputs", "outputs"],
    "template": ["output_format", "sections"],
    "guardrail": ["check_type", "severity"],
    "channel": ["platform"],
}


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_skill(skill: Skill) -> ValidationResult:
    """Validate a parsed Skill object."""
    result = ValidationResult()

    # Common field checks
    if not skill.name:
        result.add_error("Missing required field: name")
    if skill.type not in VALID_TYPES:
        result.add_error(f"Invalid type '{skill.type}' — must be one of {VALID_TYPES}")
    if not skill.domain:
        result.add_error("Missing required field: domain")
    if skill.version < 1:
        result.add_error("Version must be >= 1")
    if not skill.description:
        result.add_warning("Missing description — skill will be harder to discover")

    # Type-specific checks
    required_keys = _TYPE_REQUIRED.get(skill.type, [])
    for key in required_keys:
        if key not in skill.metadata:
            result.add_warning(f"Missing recommended metadata for {skill.type} skill: {key}")

    # Body check
    if len(skill.body) < 20:
        result.add_warning("Skill body is very short — agents benefit from richer context")

    return result
