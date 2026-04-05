"""Clinical computation tools — NEWS2, qSOFA, drug interaction checking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NEWS2Result:
    total_score: int
    risk_level: str
    component_scores: dict[str, int]
    clinical_response: str


def compute_news2(
    *,
    respiratory_rate: float,
    spo2: float,
    on_supplemental_o2: bool,
    systolic_bp: float,
    heart_rate: float,
    consciousness: str,
    temperature: float,
) -> NEWS2Result:
    """Compute NEWS2 score from vital signs."""
    scores: dict[str, int] = {}

    # Respiratory rate
    if respiratory_rate <= 8:
        scores["respiratory_rate"] = 3
    elif respiratory_rate <= 11:
        scores["respiratory_rate"] = 1
    elif respiratory_rate <= 20:
        scores["respiratory_rate"] = 0
    elif respiratory_rate <= 24:
        scores["respiratory_rate"] = 2
    else:
        scores["respiratory_rate"] = 3

    # SpO2 (Scale 1 — no supplemental O2)
    if not on_supplemental_o2:
        if spo2 <= 91:
            scores["spo2"] = 3
        elif spo2 <= 93:
            scores["spo2"] = 2
        elif spo2 <= 95:
            scores["spo2"] = 1
        else:
            scores["spo2"] = 0
    else:
        # Scale 2 — on supplemental O2
        if spo2 <= 83:
            scores["spo2"] = 3
        elif spo2 <= 85:
            scores["spo2"] = 2
        elif spo2 <= 87:
            scores["spo2"] = 1
        elif spo2 <= 92:
            scores["spo2"] = 0
        elif spo2 <= 94:
            scores["spo2"] = 1
        elif spo2 <= 96:
            scores["spo2"] = 2
        else:
            scores["spo2"] = 3

    # Supplemental O2
    scores["supplemental_o2"] = 2 if on_supplemental_o2 else 0

    # Systolic BP
    if systolic_bp <= 90:
        scores["systolic_bp"] = 3
    elif systolic_bp <= 100:
        scores["systolic_bp"] = 2
    elif systolic_bp <= 110:
        scores["systolic_bp"] = 1
    elif systolic_bp <= 219:
        scores["systolic_bp"] = 0
    else:
        scores["systolic_bp"] = 3

    # Heart rate
    if heart_rate <= 40:
        scores["heart_rate"] = 3
    elif heart_rate <= 50:
        scores["heart_rate"] = 1
    elif heart_rate <= 90:
        scores["heart_rate"] = 0
    elif heart_rate <= 110:
        scores["heart_rate"] = 1
    elif heart_rate <= 130:
        scores["heart_rate"] = 2
    else:
        scores["heart_rate"] = 3

    # Consciousness (ACVPU)
    scores["consciousness"] = 0 if consciousness.upper() == "ALERT" else 3

    # Temperature
    if temperature <= 35.0:
        scores["temperature"] = 3
    elif temperature <= 36.0:
        scores["temperature"] = 1
    elif temperature <= 38.0:
        scores["temperature"] = 0
    elif temperature <= 39.0:
        scores["temperature"] = 1
    else:
        scores["temperature"] = 2

    total = sum(scores.values())
    max_single = max(scores.values())

    # Risk level
    if total >= 7:
        risk_level = "high"
        response = "Emergency response — continuous monitoring, senior clinician review"
    elif total >= 5:
        risk_level = "medium"
        response = "Urgent response — increased monitoring frequency, clinician review within 30 min"
    elif max_single >= 3:
        risk_level = "low-medium"
        response = "Urgent ward assessment — review by ward clinician"
    else:
        risk_level = "low"
        response = "Routine monitoring — continue standard care"

    return NEWS2Result(
        total_score=total,
        risk_level=risk_level,
        component_scores=scores,
        clinical_response=response,
    )


@dataclass
class qSOFAResult:
    score: int
    positive: bool
    components: dict[str, bool]


def compute_qsofa(
    *,
    respiratory_rate: float,
    systolic_bp: float,
    altered_mental_status: bool,
) -> qSOFAResult:
    """Compute qSOFA score for sepsis screening."""
    components = {
        "respiratory_rate_ge_22": respiratory_rate >= 22,
        "systolic_bp_le_100": systolic_bp <= 100,
        "altered_mental_status": altered_mental_status,
    }
    score = sum(1 for v in components.values() if v)
    return qSOFAResult(score=score, positive=score >= 2, components=components)
