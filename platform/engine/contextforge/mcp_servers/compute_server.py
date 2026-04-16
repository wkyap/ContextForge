"""MCP tool server — Deterministic computation operations."""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NEWS2 lookup tables (Royal College of Physicians specification)
# Each parameter maps measured value to a score 0-3.
# ---------------------------------------------------------------------------

_NEWS2_RESP_RATE: list[tuple[tuple[float, float], int]] = [
    ((0, 8), 3),
    ((9, 11), 1),
    ((12, 20), 0),
    ((21, 24), 2),
    ((25, float("inf")), 3),
]

_NEWS2_SPO2_SCALE1: list[tuple[tuple[float, float], int]] = [
    ((0, 91), 3),
    ((92, 93), 2),
    ((94, 95), 1),
    ((96, float("inf")), 0),
]

_NEWS2_SPO2_SCALE2: list[tuple[tuple[float, float], int]] = [
    ((0, 83), 3),
    ((84, 85), 2),
    ((86, 87), 1),
    ((88, 92), 0),
    ((93, 94), 1),
    ((95, 96), 2),
    ((97, float("inf")), 3),
]

_NEWS2_AIR_OR_OXYGEN: dict[str, int] = {
    "air": 0,
    "oxygen": 2,
}

_NEWS2_SYSTOLIC_BP: list[tuple[tuple[float, float], int]] = [
    ((0, 90), 3),
    ((91, 100), 2),
    ((101, 110), 1),
    ((111, 219), 0),
    ((220, float("inf")), 3),
]

_NEWS2_HEART_RATE: list[tuple[tuple[float, float], int]] = [
    ((0, 40), 3),
    ((41, 50), 1),
    ((51, 90), 0),
    ((91, 110), 1),
    ((111, 130), 2),
    ((131, float("inf")), 3),
]

_NEWS2_CONSCIOUSNESS: dict[str, int] = {
    "alert": 0,
    "cvpu": 3,
    "confusion": 3,
    "voice": 3,
    "pain": 3,
    "unresponsive": 3,
}

_NEWS2_TEMPERATURE: list[tuple[tuple[float, float], int]] = [
    ((0, 35.0), 3),
    ((35.1, 36.0), 1),
    ((36.1, 38.0), 0),
    ((38.1, 39.0), 1),
    ((39.1, float("inf")), 2),
]


def _score_from_ranges(
    value: float, ranges: list[tuple[tuple[float, float], int]]
) -> int:
    """Look up score from a list of (low, high) -> score ranges."""
    for (low, high), score in ranges:
        if low <= value <= high:
            return score
    raise ValueError(f"Value {value} out of expected range")


class ComputeTools:
    """Tool definitions for deterministic computation, exposed to agents."""

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculate_news2",
                    "description": (
                        "Calculate the NEWS2 (National Early Warning Score 2) "
                        "clinical score from physiological parameters"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resp_rate": {
                                "type": "number",
                                "description": "Respiratory rate (breaths/min)",
                            },
                            "spo2": {
                                "type": "number",
                                "description": "Oxygen saturation (%)",
                            },
                            "spo2_scale": {
                                "type": "integer",
                                "enum": [1, 2],
                                "default": 1,
                                "description": (
                                    "SpO2 scale: 1 (default) or 2 "
                                    "(for hypercapnic respiratory failure)"
                                ),
                            },
                            "air_or_oxygen": {
                                "type": "string",
                                "enum": ["air", "oxygen"],
                                "description": "Whether patient is on air or supplemental oxygen",
                            },
                            "systolic_bp": {
                                "type": "number",
                                "description": "Systolic blood pressure (mmHg)",
                            },
                            "heart_rate": {
                                "type": "number",
                                "description": "Heart rate (beats/min)",
                            },
                            "consciousness": {
                                "type": "string",
                                "enum": [
                                    "alert", "cvpu", "confusion",
                                    "voice", "pain", "unresponsive",
                                ],
                                "description": "Level of consciousness (ACVPU scale)",
                            },
                            "temperature": {
                                "type": "number",
                                "description": "Body temperature (degrees Celsius)",
                            },
                        },
                        "required": [
                            "resp_rate",
                            "spo2",
                            "air_or_oxygen",
                            "systolic_bp",
                            "heart_rate",
                            "consciousness",
                            "temperature",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_qsofa",
                    "description": (
                        "Calculate the qSOFA (quick Sequential Organ Failure Assessment) "
                        "sepsis screening score"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resp_rate": {
                                "type": "number",
                                "description": "Respiratory rate (breaths/min)",
                            },
                            "systolic_bp": {
                                "type": "number",
                                "description": "Systolic blood pressure (mmHg)",
                            },
                            "altered_mentation": {
                                "type": "boolean",
                                "description": "Whether patient has altered mentation (GCS < 15)",
                            },
                        },
                        "required": ["resp_rate", "systolic_bp", "altered_mentation"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_oee",
                    "description": (
                        "Calculate Overall Equipment Effectiveness (OEE) "
                        "from availability, performance, and quality factors"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "planned_production_time": {
                                "type": "number",
                                "description": "Total planned production time (minutes)",
                            },
                            "run_time": {
                                "type": "number",
                                "description": "Actual run time (minutes)",
                            },
                            "total_count": {
                                "type": "integer",
                                "description": "Total units produced",
                            },
                            "ideal_cycle_time": {
                                "type": "number",
                                "description": "Ideal cycle time per unit (minutes)",
                            },
                            "good_count": {
                                "type": "integer",
                                "description": "Number of good (non-defective) units",
                            },
                        },
                        "required": [
                            "planned_production_time",
                            "run_time",
                            "total_count",
                            "ideal_cycle_time",
                            "good_count",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generic_compute",
                    "description": (
                        "Execute a deterministic mathematical formula. "
                        "Supports basic arithmetic, math functions (sqrt, log, pow, etc.), "
                        "and variable substitution."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "formula": {
                                "type": "string",
                                "description": "Mathematical expression, e.g. '(a + b) / c'",
                            },
                            "variables": {
                                "type": "object",
                                "description": "Mapping of variable names to numeric values",
                                "additionalProperties": {"type": "number"},
                            },
                        },
                        "required": ["formula", "variables"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "calculate_news2":
            return self._calculate_news2(args)
        elif tool_name == "calculate_qsofa":
            return self._calculate_qsofa(args)
        elif tool_name == "calculate_oee":
            return self._calculate_oee(args)
        elif tool_name == "generic_compute":
            return self._generic_compute(args)
        raise ValueError(f"Unknown tool: {tool_name}")

    # ------------------------------------------------------------------
    # NEWS2
    # ------------------------------------------------------------------

    def _calculate_news2(self, args: dict[str, Any]) -> dict[str, Any]:
        scale = args.get("spo2_scale", 1)
        spo2_table = _NEWS2_SPO2_SCALE1 if scale == 1 else _NEWS2_SPO2_SCALE2

        subscores = {
            "respiration_rate": _score_from_ranges(args["resp_rate"], _NEWS2_RESP_RATE),
            "spo2": _score_from_ranges(args["spo2"], spo2_table),
            "air_or_oxygen": _NEWS2_AIR_OR_OXYGEN[args["air_or_oxygen"].lower()],
            "systolic_bp": _score_from_ranges(args["systolic_bp"], _NEWS2_SYSTOLIC_BP),
            "heart_rate": _score_from_ranges(args["heart_rate"], _NEWS2_HEART_RATE),
            "consciousness": _NEWS2_CONSCIOUSNESS[args["consciousness"].lower()],
            "temperature": _score_from_ranges(args["temperature"], _NEWS2_TEMPERATURE),
        }

        total = sum(subscores.values())

        if total >= 7:
            clinical_risk = "high"
        elif total >= 5:
            clinical_risk = "medium"
        elif any(v == 3 for v in subscores.values()):
            clinical_risk = "low-medium"
        else:
            clinical_risk = "low"

        logger.info("NEWS2 calculated: total=%d risk=%s", total, clinical_risk)
        return {
            "total_score": total,
            "clinical_risk": clinical_risk,
            "subscores": subscores,
            "spo2_scale_used": scale,
        }

    # ------------------------------------------------------------------
    # qSOFA
    # ------------------------------------------------------------------

    def _calculate_qsofa(self, args: dict[str, Any]) -> dict[str, Any]:
        score = 0
        criteria: dict[str, bool] = {}

        criteria["respiratory_rate_ge_22"] = args["resp_rate"] >= 22
        if criteria["respiratory_rate_ge_22"]:
            score += 1

        criteria["systolic_bp_le_100"] = args["systolic_bp"] <= 100
        if criteria["systolic_bp_le_100"]:
            score += 1

        criteria["altered_mentation"] = bool(args["altered_mentation"])
        if criteria["altered_mentation"]:
            score += 1

        positive_screen = score >= 2
        logger.info("qSOFA calculated: score=%d positive=%s", score, positive_screen)
        return {
            "score": score,
            "positive_screen": positive_screen,
            "criteria": criteria,
        }

    # ------------------------------------------------------------------
    # OEE
    # ------------------------------------------------------------------

    def _calculate_oee(self, args: dict[str, Any]) -> dict[str, Any]:
        planned = args["planned_production_time"]
        run = args["run_time"]
        total_count = args["total_count"]
        ideal_cycle = args["ideal_cycle_time"]
        good = args["good_count"]

        availability = run / planned if planned > 0 else 0.0
        performance = (ideal_cycle * total_count) / run if run > 0 else 0.0
        quality = good / total_count if total_count > 0 else 0.0
        oee = availability * performance * quality

        logger.info("OEE calculated: %.2f%%", oee * 100)
        return {
            "oee": round(oee, 4),
            "availability": round(availability, 4),
            "performance": round(performance, 4),
            "quality": round(quality, 4),
            "oee_percent": round(oee * 100, 2),
        }

    # ------------------------------------------------------------------
    # Generic compute
    # ------------------------------------------------------------------

    _SAFE_NAMES: dict[str, Any] = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "pow": math.pow,
        "exp": math.exp,
        "ceil": math.ceil,
        "floor": math.floor,
        "pi": math.pi,
        "e": math.e,
    }

    def _generic_compute(self, args: dict[str, Any]) -> dict[str, Any]:
        formula: str = args["formula"]
        variables: dict[str, float] = args.get("variables", {})

        # Build a restricted namespace with math helpers and user variables
        namespace: dict[str, Any] = {**self._SAFE_NAMES, **variables}
        namespace["__builtins__"] = {}  # block builtins for safety

        try:
            result = eval(formula, namespace)  # noqa: S307
        except Exception as exc:
            logger.warning("generic_compute failed for formula=%r: %s", formula, exc)
            return {"error": str(exc), "formula": formula}

        logger.info("generic_compute: %s = %s", formula, result)
        return {"result": result, "formula": formula, "variables": variables}
