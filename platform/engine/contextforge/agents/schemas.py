"""Pydantic output schemas for PydanticAI agents.

Every specialist agent has a typed output_type. If the LLM produces
invalid output, PydanticAI auto-retries with the validation error fed back.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OrchestratorPlan(BaseModel):
    """Orchestrator's typed plan — validated, not hoped for."""

    intent: str = Field(description="What the user wants to accomplish")
    specialists_needed: list[str] = Field(
        description="Which specialists to invoke: retrieval, analysis, action"
    )
    skills_to_load: list[str] = Field(
        default_factory=list,
        description="SKILL.md files to load for this query",
    )
    reasoning: str = Field(description="Why this plan was chosen")


class RetrievalResult(BaseModel):
    """Structured retrieval output — every field validated."""

    entities_found: list[dict[str, Any]] = Field(
        default_factory=list, description="Resolved entities from KG"
    )
    time_series_data: list[dict[str, Any]] | None = Field(default=None)
    vector_results: list[dict[str, Any]] | None = Field(default=None)
    graph_paths: list[dict[str, Any]] | None = Field(default=None)
    community_summaries: list[str] | None = Field(default=None)
    confidence: float = Field(ge=0.0, le=1.0, description="Retrieval confidence")
    sources: list[str] = Field(
        default_factory=list, description="Provenance trail for citations"
    )


class AnalysisResult(BaseModel):
    """Analysis output — deterministic scores are validated as computed."""

    findings: list[str] = Field(description="Key findings from analysis")
    computed_scores: dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic scores (NEWS2, OEE, etc.) — NOT LLM-inferred",
    )
    correlations: list[dict[str, Any]] | None = Field(default=None)
    root_cause_hypothesis: str | None = Field(default=None)
    confidence: float = Field(ge=0.0, le=1.0)


class ActionResult(BaseModel):
    """Action recommendation — structured for downstream consumption."""

    recommendation: str = Field(description="What to do next")
    matched_sops: list[str] = Field(default_factory=list)
    urgency: str = Field(description="low | medium | high | critical")
    evidence_summary: str = Field(description="Why this action is recommended")
    requires_human_approval: bool = Field(default=False)


class CompressedContext(BaseModel):
    """Structured compression output — every field is useful."""

    key_entities: list[dict[str, Any]] = Field(description="Resolved entities with IDs")
    numeric_values: list[dict[str, Any]] = Field(description="Measurements with timestamps")
    relationships: list[dict[str, Any]] = Field(description="Entity-entity connections")
    alerts_and_alarms: list[dict[str, Any]] = Field(
        default_factory=list, description="Active alerts in time order"
    )
    relevant_procedures: list[str] = Field(
        default_factory=list, description="SOP/guideline references"
    )
