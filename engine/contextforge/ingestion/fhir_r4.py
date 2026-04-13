"""FHIR R4 Bundle ingester — parse resources and load into the temporal KG."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.knowledge.temporal_graph import TemporalGraph

logger = logging.getLogger(__name__)

# FHIR resource type → entity_type mapping.
RESOURCE_MAP: dict[str, str] = {
    "Patient": "Patient",
    "Encounter": "Encounter",
    "Observation": "Observation",
    "Condition": "Condition",
    "MedicationRequest": "Medication",
}


class FHIRIngester:
    """Ingest FHIR R4 Bundles into the temporal knowledge graph."""

    def __init__(self, graph: TemporalGraph) -> None:
        self._graph = graph

    async def ingest_bundle(self, bundle: dict[str, Any]) -> dict[str, int]:
        """Parse a FHIR Bundle and create entities. Returns per-type counts."""
        entries = bundle.get("entry", [])
        counts: dict[str, int] = {}

        for entry in entries:
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType", "")

            if resource_type not in RESOURCE_MAP:
                continue

            entity_type = RESOURCE_MAP[resource_type]
            props = self._extract_properties(resource_type, resource)

            await self._graph.create_entity(
                entity_type=entity_type,
                properties=props,
                source_system="fhir_r4",
                source_id=resource.get("id", ""),
                changed_by="fhir_ingester",
            )
            counts[entity_type] = counts.get(entity_type, 0) + 1

        logger.info("FHIR bundle ingested: %s", counts)
        return counts

    def _extract_properties(
        self, resource_type: str, resource: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract entity properties from a FHIR resource."""
        extractors = {
            "Patient": self._extract_patient,
            "Encounter": self._extract_encounter,
            "Observation": self._extract_observation,
            "Condition": self._extract_condition,
            "MedicationRequest": self._extract_medication,
        }
        extractor = extractors.get(resource_type)
        if extractor:
            return extractor(resource)
        return {"id": resource.get("id", "")}

    def _extract_patient(self, r: dict[str, Any]) -> dict[str, Any]:
        name = (r.get("name") or [{}])[0]
        return {
            "id": r.get("id", ""),
            "name": f"{' '.join(name.get('given', []))} {name.get('family', '')}".strip(),
            "given_name": (name.get("given") or [""])[0],
            "family_name": name.get("family", ""),
            "date_of_birth": r.get("birthDate", ""),
            "gender": r.get("gender", ""),
            "mrn": self._get_identifier(r, "MR"),
        }

    def _extract_encounter(self, r: dict[str, Any]) -> dict[str, Any]:
        period = r.get("period", {})
        return {
            "id": r.get("id", ""),
            "encounter_id": r.get("id", ""),
            "status": r.get("status", ""),
            "class": (r.get("class", {}) or {}).get("code", ""),
            "start_time": period.get("start", ""),
            "end_time": period.get("end"),
        }

    def _extract_observation(self, r: dict[str, Any]) -> dict[str, Any]:
        coding = ((r.get("code", {}).get("coding")) or [{}])[0]
        vq = r.get("valueQuantity", {})
        return {
            "id": r.get("id", ""),
            "observation_id": r.get("id", ""),
            "status": r.get("status", ""),
            "category": self._get_category(r),
            "code": coding.get("code", ""),
            "code_display": coding.get("display", ""),
            "value": vq.get("value"),
            "unit": vq.get("unit", ""),
            "effective_time": r.get("effectiveDateTime", ""),
        }

    def _extract_condition(self, r: dict[str, Any]) -> dict[str, Any]:
        coding = ((r.get("code", {}).get("coding")) or [{}])[0]
        return {
            "id": r.get("id", ""),
            "condition_id": r.get("id", ""),
            "code": coding.get("code", ""),
            "code_system": coding.get("system", ""),
            "display": coding.get("display", ""),
            "clinical_status": (
                (r.get("clinicalStatus", {}).get("coding") or [{}])[0].get("code", "")
            ),
            "recorded_date": r.get("recordedDate", ""),
        }

    def _extract_medication(self, r: dict[str, Any]) -> dict[str, Any]:
        coding = ((r.get("medicationCodeableConcept", {}).get("coding")) or [{}])[0]
        return {
            "id": r.get("id", ""),
            "medication_id": r.get("id", ""),
            "code": coding.get("code", ""),
            "display": coding.get("display", ""),
            "status": r.get("status", ""),
            "start_date": r.get("authoredOn", ""),
        }

    @staticmethod
    def _get_identifier(resource: dict[str, Any], type_code: str) -> str:
        for ident in resource.get("identifier", []):
            if (ident.get("type", {}).get("coding") or [{}])[0].get("code") == type_code:
                return str(ident.get("value", ""))
        return ""

    @staticmethod
    def _get_category(observation: dict[str, Any]) -> str:
        cats = observation.get("category", [])
        if cats:
            codings = cats[0].get("coding", [])
            if codings:
                return str(codings[0].get("code", ""))
        return ""
