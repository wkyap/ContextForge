"""SSG Skills Framework taxonomy loader — imports skill hierarchy into Neo4j."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.db.neo4j import Neo4jClient
from contextforge.db.postgres import PostgresClient
from contextforge.ingestion.base_ingester import BaseIngester, IngestResult

logger = logging.getLogger(__name__)

# ── SSG Skills Framework seed data ──────────────────────────────────────────
# Simplified taxonomy based on SkillsFuture Singapore framework.
# In production, this would be loaded from SSG's official API or Excel export.

SSG_TAXONOMY: list[dict[str, Any]] = [
    # ── ICT Sector ─────────────────────────────────────────────────
    {
        "id": "ssg:ict",
        "name": "Information and Communications Technology",
        "category": "sector",
        "parent": None,
    },
    {
        "id": "ssg:ict:software-dev",
        "name": "Software Development",
        "category": "technical",
        "parent": "ssg:ict",
    },
    {
        "id": "ssg:ict:python",
        "name": "Python Programming",
        "category": "technical",
        "parent": "ssg:ict:software-dev",
    },
    {
        "id": "ssg:ict:javascript",
        "name": "JavaScript Development",
        "category": "technical",
        "parent": "ssg:ict:software-dev",
    },
    {
        "id": "ssg:ict:java",
        "name": "Java Programming",
        "category": "technical",
        "parent": "ssg:ict:software-dev",
    },
    {
        "id": "ssg:ict:sql",
        "name": "SQL & Database Management",
        "category": "technical",
        "parent": "ssg:ict:software-dev",
    },
    {
        "id": "ssg:ict:cloud",
        "name": "Cloud Computing",
        "category": "technical",
        "parent": "ssg:ict",
    },
    {
        "id": "ssg:ict:aws",
        "name": "Amazon Web Services",
        "category": "technical",
        "parent": "ssg:ict:cloud",
    },
    {
        "id": "ssg:ict:azure",
        "name": "Microsoft Azure",
        "category": "technical",
        "parent": "ssg:ict:cloud",
    },
    {
        "id": "ssg:ict:data-analytics",
        "name": "Data Analytics",
        "category": "technical",
        "parent": "ssg:ict",
    },
    {
        "id": "ssg:ict:data-viz",
        "name": "Data Visualisation",
        "category": "technical",
        "parent": "ssg:ict:data-analytics",
    },
    {
        "id": "ssg:ict:ml",
        "name": "Machine Learning",
        "category": "technical",
        "parent": "ssg:ict:data-analytics",
    },
    {
        "id": "ssg:ict:cybersecurity",
        "name": "Cybersecurity",
        "category": "technical",
        "parent": "ssg:ict",
    },
    {
        "id": "ssg:ict:networking",
        "name": "Network Administration",
        "category": "technical",
        "parent": "ssg:ict",
    },
    {
        "id": "ssg:ict:ux-design",
        "name": "UX/UI Design",
        "category": "technical",
        "parent": "ssg:ict",
    },
    # ── Professional Services ──────────────────────────────────────
    {
        "id": "ssg:prof",
        "name": "Professional Services",
        "category": "sector",
        "parent": None,
    },
    {
        "id": "ssg:prof:accounting",
        "name": "Accounting & Finance",
        "category": "technical",
        "parent": "ssg:prof",
    },
    {
        "id": "ssg:prof:bookkeeping",
        "name": "Bookkeeping",
        "category": "technical",
        "parent": "ssg:prof:accounting",
    },
    {
        "id": "ssg:prof:tax",
        "name": "Tax Filing & Compliance",
        "category": "technical",
        "parent": "ssg:prof:accounting",
    },
    {
        "id": "ssg:prof:audit",
        "name": "Auditing",
        "category": "technical",
        "parent": "ssg:prof:accounting",
    },
    {
        "id": "ssg:prof:hr",
        "name": "Human Resource Management",
        "category": "technical",
        "parent": "ssg:prof",
    },
    {
        "id": "ssg:prof:marketing",
        "name": "Digital Marketing",
        "category": "technical",
        "parent": "ssg:prof",
    },
    {
        "id": "ssg:prof:seo",
        "name": "Search Engine Optimisation",
        "category": "technical",
        "parent": "ssg:prof:marketing",
    },
    {
        "id": "ssg:prof:project-mgmt",
        "name": "Project Management",
        "category": "technical",
        "parent": "ssg:prof",
    },
    # ── Tourism & Hospitality ──────────────────────────────────────
    {
        "id": "ssg:tourism",
        "name": "Tourism & Hospitality",
        "category": "sector",
        "parent": None,
    },
    {
        "id": "ssg:tourism:hotel-ops",
        "name": "Hotel Operations",
        "category": "technical",
        "parent": "ssg:tourism",
    },
    {
        "id": "ssg:tourism:f-and-b",
        "name": "Food & Beverage Service",
        "category": "technical",
        "parent": "ssg:tourism",
    },
    {
        "id": "ssg:tourism:events",
        "name": "Events Management",
        "category": "technical",
        "parent": "ssg:tourism",
    },
    {
        "id": "ssg:tourism:travel",
        "name": "Travel Agency Operations",
        "category": "technical",
        "parent": "ssg:tourism",
    },
    # ── Retail ─────────────────────────────────────────────────────
    {
        "id": "ssg:retail",
        "name": "Retail",
        "category": "sector",
        "parent": None,
    },
    {
        "id": "ssg:retail:sales",
        "name": "Retail Sales",
        "category": "technical",
        "parent": "ssg:retail",
    },
    {
        "id": "ssg:retail:ecommerce",
        "name": "E-Commerce Management",
        "category": "technical",
        "parent": "ssg:retail",
    },
    {
        "id": "ssg:retail:merchandising",
        "name": "Visual Merchandising",
        "category": "technical",
        "parent": "ssg:retail",
    },
    {
        "id": "ssg:retail:inventory",
        "name": "Inventory Management",
        "category": "technical",
        "parent": "ssg:retail",
    },
    # ── Cross-sector Soft Skills ───────────────────────────────────
    {
        "id": "ssg:soft",
        "name": "Soft Skills & Workplace Competencies",
        "category": "sector",
        "parent": None,
    },
    {
        "id": "ssg:soft:communication",
        "name": "Business Communication",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:teamwork",
        "name": "Teamwork & Collaboration",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:leadership",
        "name": "Leadership",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:problem-solving",
        "name": "Problem Solving",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:adaptability",
        "name": "Adaptability & Resilience",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:critical-thinking",
        "name": "Critical Thinking",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:time-mgmt",
        "name": "Time Management",
        "category": "soft",
        "parent": "ssg:soft",
    },
    {
        "id": "ssg:soft:customer-service",
        "name": "Customer Service",
        "category": "soft",
        "parent": "ssg:soft",
    },
]

# ── Cross-domain transferability edges ──────────────────────────────────────
TRANSFER_EDGES: list[tuple[str, str]] = [
    ("ssg:ict:data-analytics", "ssg:prof:accounting"),
    ("ssg:ict:python", "ssg:ict:data-analytics"),
    ("ssg:prof:marketing", "ssg:retail:ecommerce"),
    ("ssg:prof:project-mgmt", "ssg:tourism:events"),
    ("ssg:soft:customer-service", "ssg:retail:sales"),
    ("ssg:soft:customer-service", "ssg:tourism:hotel-ops"),
    ("ssg:soft:communication", "ssg:prof:hr"),
    ("ssg:ict:ux-design", "ssg:prof:marketing"),
    ("ssg:retail:ecommerce", "ssg:ict:data-analytics"),
]


class SSGTaxonomyLoader(BaseIngester):
    """Load SSG Skills Framework taxonomy into Neo4j as a skill hierarchy."""

    def __init__(self, neo4j: Neo4jClient, postgres: PostgresClient) -> None:
        super().__init__(source_name="ssg_taxonomy")
        self._neo4j = neo4j
        self._postgres = postgres

    async def validate(self, data: Any) -> bool:
        return isinstance(data, list) and all(
            isinstance(s, dict) and "id" in s and "name" in s for s in data
        )

    async def ingest(self, data: Any) -> IngestResult:
        skills: list[dict[str, Any]] = data
        result = IngestResult()

        # Create skill nodes
        for skill in skills:
            try:
                await self._neo4j.execute_write(
                    """MERGE (s:Skill:Entity {id: $id})
                       ON CREATE SET
                           s.name = $name,
                           s.category = $category,
                           s.ssg_framework_code = $id,
                           s._is_current = true,
                           s._created_at = datetime(),
                           s._type = 'Skill',
                           s._version = 1
                       ON MATCH SET
                           s.name = $name,
                           s.category = $category""",
                    {
                        "id": skill["id"],
                        "name": skill["name"],
                        "category": skill.get("category", "technical"),
                    },
                )
                result.entities_created += 1
            except Exception as exc:
                result.errors.append(
                    f"Failed to create skill {skill['id']}: {exc}",
                )

        # Create PARENT_OF hierarchy edges
        for skill in skills:
            if skill.get("parent"):
                try:
                    await self._neo4j.execute_write(
                        """MATCH (parent:Skill {id: $parent_id})
                           MATCH (child:Skill {id: $child_id})
                           MERGE (parent)-[:PARENT_OF]->(child)""",
                        {"parent_id": skill["parent"], "child_id": skill["id"]},
                    )
                    result.relationships_created += 1
                except Exception as exc:
                    result.errors.append(
                        f"Failed to link {skill['parent']} -> {skill['id']}: {exc}"
                    )

        # Create TRANSFERS_TO cross-domain edges
        for from_id, to_id in TRANSFER_EDGES:
            try:
                await self._neo4j.execute_write(
                    """MATCH (a:Skill {id: $from_id})
                       MATCH (b:Skill {id: $to_id})
                       MERGE (a)-[:TRANSFERS_TO]->(b)""",
                    {"from_id": from_id, "to_id": to_id},
                )
                result.relationships_created += 1
            except Exception as exc:
                result.errors.append(
                    f"Failed transfer edge {from_id} -> {to_id}: {exc}",
                )

        logger.info(
            "SSG taxonomy loaded: %d skills, %d relationships, %d errors",
            result.entities_created,
            result.relationships_created,
            len(result.errors),
        )
        return result


async def load_ssg_taxonomy(
    neo4j: Neo4jClient, postgres: PostgresClient,
) -> IngestResult:
    """Convenience function to load the default SSG taxonomy."""
    loader = SSGTaxonomyLoader(neo4j, postgres)
    return await loader.safe_ingest(SSG_TAXONOMY)
