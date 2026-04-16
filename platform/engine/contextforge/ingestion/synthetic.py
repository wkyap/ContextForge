"""Synthetic patient data generator for development and testing."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any


def _random_date(start_year: int = 1940, end_year: int = 2005) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


_GIVEN_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer",
                "Michael", "Linda", "David", "Elizabeth", "Sarah", "Thomas"]
_FAMILY_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                 "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Moore"]
_CONDITIONS = [
    ("J18.9", "Pneumonia, unspecified"),
    ("I10", "Essential hypertension"),
    ("E11.9", "Type 2 diabetes mellitus"),
    ("J44.1", "COPD with acute exacerbation"),
    ("I50.9", "Heart failure, unspecified"),
    ("N17.9", "Acute kidney failure, unspecified"),
    ("K92.1", "Melaena (GI bleed)"),
    ("A41.9", "Sepsis, unspecified"),
]
_MEDICATIONS = [
    ("Amoxicillin 500mg", "oral", "three times daily"),
    ("Metformin 500mg", "oral", "twice daily"),
    ("Amlodipine 5mg", "oral", "once daily"),
    ("Salbutamol 100mcg", "inhaled", "as needed"),
    ("Paracetamol 1g", "oral", "four times daily"),
    ("Enoxaparin 40mg", "subcutaneous", "once daily"),
    ("Furosemide 40mg", "oral", "once daily"),
]


def generate_patient() -> dict[str, Any]:
    """Generate a synthetic FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": str(uuid.uuid4()),
        "identifier": [
            {
                "type": {"coding": [{"code": "MR"}]},
                "value": f"MRN-{random.randint(100000, 999999)}",
            }
        ],
        "name": [
            {
                "given": [random.choice(_GIVEN_NAMES)],
                "family": random.choice(_FAMILY_NAMES),
            }
        ],
        "birthDate": _random_date(),
        "gender": random.choice(["male", "female"]),
    }


def generate_encounter(patient_id: str) -> dict[str, Any]:
    """Generate a synthetic FHIR Encounter resource."""
    start = datetime.now(UTC) - timedelta(hours=random.randint(1, 72))
    return {
        "resourceType": "Encounter",
        "id": str(uuid.uuid4()),
        "status": "in-progress",
        "class": {"code": random.choice(["inpatient", "emergency"])},
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": start.isoformat()},
    }


def generate_observations(patient_id: str, count: int = 10) -> list[dict[str, Any]]:
    """Generate synthetic vital-sign observations."""
    observations = []
    base_time = datetime.now(UTC) - timedelta(hours=count)
    for i in range(count):
        time = base_time + timedelta(hours=i)
        observations.extend([
            _vital("heart_rate", random.uniform(60, 110), "beats/min", patient_id, time),
            _vital("systolic_bp", random.uniform(90, 160), "mmHg", patient_id, time),
            _vital("spo2", random.uniform(92, 100), "%", patient_id, time),
            _vital("temperature", random.uniform(36.0, 39.0), "Cel", patient_id, time),
            _vital("respiratory_rate", random.uniform(12, 25), "breaths/min", patient_id, time),
        ])
    return observations


def _vital(name: str, value: float, unit: str, patient_id: str, time: datetime) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [{"coding": [{"code": "vital-signs"}]}],
        "code": {
            "coding": [{"code": name, "display": name.replace("_", " ").title()}],
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": time.isoformat(),
        "valueQuantity": {"value": round(value, 1), "unit": unit},
    }


def generate_fhir_bundle(
    num_patients: int = 5, observations_per_patient: int = 10,
) -> dict[str, Any]:
    """Generate a complete FHIR Bundle with patients, encounters, observations."""
    entries: list[dict[str, Any]] = []

    for _ in range(num_patients):
        patient = generate_patient()
        pid = patient["id"]
        entries.append({"resource": patient})

        encounter = generate_encounter(pid)
        entries.append({"resource": encounter})

        # Observations
        for obs in generate_observations(pid, observations_per_patient):
            entries.append({"resource": obs})

        # Random conditions
        for code, display in random.sample(_CONDITIONS, k=random.randint(1, 3)):
            entries.append({"resource": {
                "resourceType": "Condition",
                "id": str(uuid.uuid4()),
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "code": {"coding": [{"code": code, "system": "icd-10", "display": display}]},
                "subject": {"reference": f"Patient/{pid}"},
                "recordedDate": _now_iso(),
            }})

        # Random medications
        for drug, route, freq in random.sample(_MEDICATIONS, k=random.randint(1, 3)):
            entries.append({"resource": {
                "resourceType": "MedicationRequest",
                "id": str(uuid.uuid4()),
                "status": "active",
                "medicationCodeableConcept": {"coding": [{"display": drug}]},
                "subject": {"reference": f"Patient/{pid}"},
                "authoredOn": _now_iso(),
            }})

    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}
