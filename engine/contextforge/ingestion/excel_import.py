"""ExcelIngester — parse NTUC LearningHub Excel tracking sheets."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from contextforge.db.neo4j import Neo4jClient
from contextforge.db.postgres import PostgresClient
from contextforge.guardrails.pdpa_sg import hash_nric, mask_phone
from contextforge.ingestion.base_ingester import BaseIngester, IngestResult

logger = logging.getLogger(__name__)

# Column mappings from expected Excel headers to DB fields
TRAINEE_COLUMNS = {
    "Trainee Code": "trainee_code",
    "Name": "name",
    "Email": "email",
    "Phone": "phone",
    "NRIC": "nric",
    "Education Level": "education_level",
    "Field of Study": "field_of_study",
    "Years Experience": "years_experience",
    "Programme Type": "programme_type",
    "Career Goals": "career_goals",
    "Preferred Sectors": "preferred_sectors",
}

COURSE_COLUMNS = {
    "Course Code": "course_code",
    "Title": "title",
    "Provider": "provider",
    "Sector": "sector",
    "Duration (Weeks)": "duration_weeks",
    "Mode": "mode",
    "Skills Taught": "skills_taught",
    "SSG Course Code": "ssg_course_code",
    "Capacity": "capacity",
}

EMPLOYER_COLUMNS = {
    "Company Name": "company_name",
    "UEN": "uen",
    "Sector": "sector",
    "Size": "size",
    "Locations": "locations",
    "Partnership Tier": "partnership_tier",
    "Contact Email": "contact_email",
}


def _parse_list_field(value: Any) -> list[str]:
    """Parse a comma/semicolon-separated string into a list."""
    if isinstance(value, list):
        return value
    if not value or (isinstance(value, float) and value != value):  # NaN check
        return []
    return [s.strip() for s in str(value).replace(";", ",").split(",") if s.strip()]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class ExcelIngester(BaseIngester):
    """Import trainees, courses, or employers from Excel/CSV data.

    Expects data as a list of dicts (pre-parsed rows from openpyxl or pandas).
    The ``sheet_type`` parameter determines which column mapping to use.
    """

    def __init__(
        self,
        postgres: PostgresClient,
        neo4j: Neo4jClient,
        sheet_type: str = "trainees",
    ) -> None:
        super().__init__(source_name=f"excel_{sheet_type}")
        self._postgres = postgres
        self._neo4j = neo4j
        self._sheet_type = sheet_type

    async def validate(self, data: Any) -> bool:
        if not isinstance(data, list) or len(data) == 0:
            return False
        if not isinstance(data[0], dict):
            return False
        return True

    async def ingest(self, data: Any) -> IngestResult:
        rows: list[dict[str, Any]] = data
        if self._sheet_type == "trainees":
            return await self._ingest_trainees(rows)
        elif self._sheet_type == "courses":
            return await self._ingest_courses(rows)
        elif self._sheet_type == "employers":
            return await self._ingest_employers(rows)
        else:
            return IngestResult(errors=[f"Unknown sheet type: {self._sheet_type}"])

    async def _ingest_trainees(self, rows: list[dict[str, Any]]) -> IngestResult:
        result = IngestResult()
        for row in rows:
            try:
                trainee_id = str(uuid.uuid4())
                code = str(row.get("Trainee Code") or row.get("trainee_code", ""))
                name = str(row.get("Name") or row.get("name", ""))
                if not code or not name:
                    result.errors.append("Skipping row: missing code or name")
                    continue

                # PDPA: mask PII before storage
                raw_nric = str(row.get("NRIC") or row.get("nric", ""))
                raw_phone = str(row.get("Phone") or row.get("phone", ""))
                nric_hashed = hash_nric(raw_nric) if raw_nric else None
                phone_masked = mask_phone(raw_phone) if raw_phone else None

                email = str(row.get("Email") or row.get("email", "")) or None
                edu = str(row.get("Education Level") or row.get("education_level", "")) or None
                fos = str(row.get("Field of Study") or row.get("field_of_study", "")) or None
                yexp = _safe_int(row.get("Years Experience") or row.get("years_experience", 0))
                prog = str(row.get("Programme Type") or row.get("programme_type", "")) or None
                goals = _parse_list_field(row.get("Career Goals") or row.get("career_goals"))
                sectors = _parse_list_field(row.get("Preferred Sectors") or row.get("preferred_sectors"))

                await self._postgres.execute(
                    """INSERT INTO trainees (id, trainee_code, name, email, phone_masked,
                       nric_hash, education_level, field_of_study, years_experience,
                       career_goals, preferred_sectors, programme_type, status)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'applied')
                       ON CONFLICT (trainee_code) DO NOTHING""",
                    [
                        trainee_id, code, name, email, phone_masked,
                        nric_hashed, edu, fos, yexp, goals, sectors, prog,
                    ],
                )
                result.entities_created += 1
            except Exception as exc:
                result.errors.append(f"Trainee row error: {exc}")

        return result

    async def _ingest_courses(self, rows: list[dict[str, Any]]) -> IngestResult:
        result = IngestResult()
        for row in rows:
            try:
                course_id = str(uuid.uuid4())
                code = str(row.get("Course Code") or row.get("course_code", ""))
                title = str(row.get("Title") or row.get("title", ""))
                if not code or not title:
                    result.errors.append("Skipping row: missing code or title")
                    continue

                provider = str(row.get("Provider") or row.get("provider", "NTUC LearningHub"))
                sector = str(row.get("Sector") or row.get("sector", "")) or None
                dur = _safe_int(row.get("Duration (Weeks)") or row.get("duration_weeks"))
                mode = str(row.get("Mode") or row.get("mode", "")) or None
                skills = _parse_list_field(row.get("Skills Taught") or row.get("skills_taught"))
                ssg_code = str(row.get("SSG Course Code") or row.get("ssg_course_code", "")) or None
                capacity = _safe_int(row.get("Capacity") or row.get("capacity"))

                await self._postgres.execute(
                    """INSERT INTO courses (id, course_code, title, provider, sector,
                       duration_weeks, mode, skills_taught, ssg_course_code, capacity)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                       ON CONFLICT (course_code) DO NOTHING""",
                    [
                        course_id, code, title, provider, sector,
                        dur or None, mode, skills, ssg_code, capacity or None,
                    ],
                )
                result.entities_created += 1
            except Exception as exc:
                result.errors.append(f"Course row error: {exc}")

        return result

    async def _ingest_employers(self, rows: list[dict[str, Any]]) -> IngestResult:
        result = IngestResult()
        for row in rows:
            try:
                employer_id = str(uuid.uuid4())
                name = str(row.get("Company Name") or row.get("company_name", ""))
                if not name:
                    result.errors.append("Skipping row: missing company name")
                    continue

                uen = str(row.get("UEN") or row.get("uen", "")) or None
                sector = str(row.get("Sector") or row.get("sector", "")) or None
                size = str(row.get("Size") or row.get("size", "")) or None
                locs = _parse_list_field(row.get("Locations") or row.get("locations"))
                tier = str(row.get("Partnership Tier") or row.get("partnership_tier", "new"))
                email = str(row.get("Contact Email") or row.get("contact_email", "")) or None

                await self._postgres.execute(
                    """INSERT INTO employers (id, company_name, uen, sector, size,
                       locations, partnership_tier, contact_email)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                       ON CONFLICT (uen) DO NOTHING""",
                    [employer_id, name, uen, sector, size, locs, tier, email],
                )
                result.entities_created += 1
            except Exception as exc:
                result.errors.append(f"Employer row error: {exc}")

        return result
