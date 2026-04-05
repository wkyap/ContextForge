"""Synthetic data generator for CareerForge development and testing.

Generates realistic Singapore workforce data:
  - 5 programmes
  - 30 courses
  - 50 employers
  - 200 trainees
  - 120 placements
  - 80 job openings
"""

from __future__ import annotations

import hashlib
import logging
import random
import uuid
from datetime import date, timedelta
from typing import Any

from contextforge.db.postgres import PostgresClient

logger = logging.getLogger(__name__)

# ── Seed data pools ─────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Wei Ming", "Mei Ling", "Raj", "Priya", "Ahmad", "Siti", "Jun Wei",
    "Hui Ling", "Kumar", "Lakshmi", "Hafiz", "Nurul", "Zhi Hao", "Xin Yi",
    "Arjun", "Deepa", "Ismail", "Fatimah", "Yi Xuan", "Jia Ying",
    "Ravi", "Anita", "Faizal", "Aisyah", "Kai Wen", "Xiao Ting",
    "Vikram", "Shalini", "Rizwan", "Amirah", "Zheng Wei", "Pei Shan",
    "Suresh", "Kavitha", "Firdaus", "Mariam", "Hao Yu", "Wen Xin",
    "Dinesh", "Meera",
]

LAST_NAMES = [
    "Tan", "Lim", "Lee", "Wong", "Ng", "Goh", "Chua", "Chan", "Koh", "Teo",
    "Ong", "Yeo", "Sim", "Ho", "Tay", "Wee", "Foo", "Low", "Chin", "Chong",
    "Singh", "Kaur", "Sharma", "Kumar", "Nair", "Pillai", "Menon", "Rao",
    "Ibrahim", "Mohamed", "Abdullah", "Hassan", "Rahman", "Yusof", "Ali",
]

SECTORS = ["ICT", "Professional Services", "Tourism", "Retail", "Healthcare"]

PROGRAMME_TYPES = ["SCTP", "Place-and-Train", "Employer-led"]

EDUCATION_LEVELS = [
    "O-Level", "N-Level", "Nitec", "Higher Nitec", "Diploma",
    "Bachelor's", "Master's", "PhD",
]

COMPANY_NAMES = [
    "TechNova Solutions", "Singtel Digital", "DBS Tech Hub", "Grab Engineering",
    "Shopee Singapore", "Sea Group", "Razer Inc", "Ninjavan Tech",
    "Acronis Asia", "Carousell", "PropertyGuru", "Foodpanda SG",
    "Lazada Singapore", "GoJek Tech", "Wise Asia", "ByteDance SG",
    "Tencent Cloud SG", "Amazon Web Services SG", "Google Asia",
    "Microsoft Singapore", "SAP Labs Singapore", "Accenture SG",
    "Deloitte Digital SG", "KPMG Digital", "EY Consulting",
    "PwC Advisory", "Standard Chartered Tech", "OCBC Digital",
    "UOB Innovation", "Mapletree Digital", "CapitaLand Tech",
    "Keppel Corp Digital", "SIA Engineering", "ST Engineering",
    "Sembcorp Digital", "Certis Group", "Thales Singapore",
    "Continental Automotive", "Micron Technology", "Dyson Operations",
    "Procter & Gamble SG", "Unilever Singapore", "Nestle SG",
    "Marina Bay Sands", "Resorts World Sentosa", "Mandarin Oriental",
    "Hilton Singapore", "IHG Hotels SG", "FairPrice Group",
    "Dairy Farm SG", "Courts SG",
]

COURSE_DATA = [
    ("ICT-PY01", "Python for Data Analytics", "ICT", 12, "full-time", ["Python", "Pandas", "SQL"]),
    ("ICT-JS01", "Full-Stack JavaScript", "ICT", 16, "full-time", ["JavaScript", "React", "Node.js"]),
    ("ICT-CL01", "AWS Cloud Practitioner", "ICT", 8, "part-time", ["AWS", "Cloud Computing"]),
    ("ICT-CS01", "Cybersecurity Fundamentals", "ICT", 12, "full-time", ["Network Security", "Encryption"]),
    ("ICT-DA01", "Data Analytics with Python", "ICT", 12, "full-time", ["Python", "Data Analytics", "Visualisation"]),
    ("ICT-ML01", "Machine Learning Foundations", "ICT", 16, "full-time", ["Python", "Machine Learning", "Statistics"]),
    ("ICT-UX01", "UX Design Fundamentals", "ICT", 8, "part-time", ["UX Design", "Figma", "User Research"]),
    ("ICT-DV01", "DevOps & CI/CD", "ICT", 10, "part-time", ["Docker", "Jenkins", "Git"]),
    ("ICT-AZ01", "Azure Cloud Solutions", "ICT", 8, "part-time", ["Azure", "Cloud Computing"]),
    ("ICT-NW01", "Network Administration", "ICT", 12, "full-time", ["Networking", "TCP/IP", "Cisco"]),
    ("PRO-AC01", "Professional Accounting", "Professional Services", 16, "full-time", ["Accounting", "GAAP", "SAP"]),
    ("PRO-BK01", "Bookkeeping & Payroll", "Professional Services", 8, "part-time", ["Bookkeeping", "Payroll", "QuickBooks"]),
    ("PRO-TX01", "Tax Filing & Compliance", "Professional Services", 10, "part-time", ["Tax", "IRAS", "GST"]),
    ("PRO-HR01", "Human Resource Management", "Professional Services", 12, "full-time", ["HR", "Recruitment", "Payroll"]),
    ("PRO-DM01", "Digital Marketing", "Professional Services", 12, "full-time", ["SEO", "SEM", "Social Media"]),
    ("PRO-PM01", "Project Management Professional", "Professional Services", 10, "part-time", ["PMP", "Agile", "Scrum"]),
    ("TOU-HO01", "Hotel Operations", "Tourism", 12, "full-time", ["Front Desk", "Housekeeping", "PMS"]),
    ("TOU-FB01", "F&B Service Excellence", "Tourism", 8, "full-time", ["F&B Service", "WSQ", "Hygiene"]),
    ("TOU-EV01", "Events Management", "Tourism", 10, "part-time", ["Event Planning", "Logistics", "Vendor Mgmt"]),
    ("TOU-TV01", "Travel Operations", "Tourism", 8, "full-time", ["Reservations", "Ticketing", "GDS"]),
    ("RET-RS01", "Retail Sales Professional", "Retail", 6, "full-time", ["Sales", "Customer Service", "POS"]),
    ("RET-EC01", "E-Commerce Operations", "Retail", 10, "part-time", ["E-Commerce", "Shopify", "Logistics"]),
    ("RET-VM01", "Visual Merchandising", "Retail", 6, "part-time", ["Merchandising", "Display Design"]),
    ("RET-IM01", "Inventory Management", "Retail", 8, "part-time", ["Inventory", "Supply Chain", "ERP"]),
    ("ICT-JV01", "Java Enterprise Development", "ICT", 16, "full-time", ["Java", "Spring Boot", "Microservices"]),
    ("ICT-DB01", "Database Administration", "ICT", 10, "part-time", ["PostgreSQL", "MySQL", "Database"]),
    ("PRO-AU01", "Internal Auditing", "Professional Services", 12, "part-time", ["Auditing", "Compliance", "Risk"]),
    ("TOU-CR01", "Cruise Operations", "Tourism", 8, "full-time", ["Cruise", "Maritime", "Hospitality"]),
    ("RET-LX01", "Luxury Retail Management", "Retail", 8, "part-time", ["Luxury", "Client Relations"]),
    ("ICT-AI01", "Applied AI & Automation", "ICT", 16, "full-time", ["AI", "Automation", "Python", "NLP"]),
]

JOB_TITLES = {
    "ICT": [
        "Junior Software Developer", "Data Analyst", "Cloud Engineer",
        "Cybersecurity Analyst", "Frontend Developer", "QA Engineer",
        "DevOps Engineer", "ML Engineer", "UX Designer", "Database Admin",
    ],
    "Professional Services": [
        "Junior Accountant", "Accounts Executive", "HR Executive",
        "Digital Marketing Executive", "Tax Associate", "Audit Associate",
        "Project Coordinator", "Business Analyst",
    ],
    "Tourism": [
        "Guest Service Agent", "F&B Supervisor", "Events Coordinator",
        "Travel Consultant", "Reservations Executive",
    ],
    "Retail": [
        "Retail Associate", "E-Commerce Executive", "Visual Merchandiser",
        "Inventory Coordinator", "Store Supervisor",
    ],
}

LOCATIONS = ["Central", "North", "East", "West", "Jurong", "Changi", "CBD", "Sentosa"]
WORK_ARRANGEMENTS = ["on-site", "hybrid", "remote"]


def _gen_nric() -> str:
    prefix = random.choice(["S", "T", "F", "G"])
    digits = "".join(str(random.randint(0, 9)) for _ in range(7))
    suffix = random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
    return f"{prefix}{digits}{suffix}"


def _hash(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()[:16]


async def seed_careerforge_data(postgres: PostgresClient) -> dict[str, int]:
    """Generate and insert synthetic CareerForge data. Returns counts."""
    counts: dict[str, int] = {}
    rng = random.Random(42)  # deterministic for reproducibility

    # ── Programmes ──────────────────────────────────────────────────
    programmes = [
        ("SCTP-ICT-2026", "SCTP Information & Communications Technology", "SCTP", "ICT", 75.0, "SSG"),
        ("SCTP-PRO-2026", "SCTP Professional Services", "SCTP", "Professional Services", 70.0, "SSG"),
        ("PNT-TOU-2026", "Place-and-Train Tourism & Hospitality", "Place-and-Train", "Tourism", 80.0, "WSG"),
        ("PNT-RET-2026", "Place-and-Train Retail", "Place-and-Train", "Retail", 75.0, "WSG"),
        ("EMP-ICT-2026", "Employer-Led ICT Programme", "Employer-led", "ICT", 85.0, "IMDA"),
    ]
    programme_ids: dict[str, str] = {}
    for pname, pfull, ptype, psector, target, agency in programmes:
        pid = str(uuid.uuid4())
        programme_ids[pname] = pid
        await postgres.execute(
            """INSERT INTO programmes (id, name, type, sector, target_placement_rate, reporting_agency)
               VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING""",
            [pid, pfull, ptype, psector, target, agency],
        )
    counts["programmes"] = len(programmes)

    # ── Courses ─────────────────────────────────────────────────────
    course_ids: dict[str, str] = {}
    for code, title, sector, dur, mode, skills in COURSE_DATA:
        cid = str(uuid.uuid4())
        course_ids[code] = cid
        capacity = rng.randint(20, 40)
        await postgres.execute(
            """INSERT INTO courses (id, course_code, title, provider, sector,
               duration_weeks, mode, skills_taught, capacity, current_enrolment)
               VALUES ($1,$2,$3,'NTUC LearningHub',$4,$5,$6,$7,$8,$9)
               ON CONFLICT (course_code) DO NOTHING""",
            [cid, code, title, sector, dur, mode, skills, capacity, rng.randint(0, capacity)],
        )
    counts["courses"] = len(COURSE_DATA)

    # ── Employers ───────────────────────────────────────────────────
    employer_ids: list[tuple[str, str]] = []  # (id, sector)
    for i, name in enumerate(COMPANY_NAMES):
        eid = str(uuid.uuid4())
        sector = SECTORS[i % len(SECTORS)]
        uen = f"{rng.randint(10, 99)}{rng.randint(100000, 999999)}{rng.choice('ABCDEFGHJKLMNP')}"
        size = rng.choice(["sme", "sme", "mnc", "mnc", "gov"])
        locs = rng.sample(LOCATIONS, k=rng.randint(1, 3))
        tier = rng.choice(["new", "active", "active", "preferred"])
        employer_ids.append((eid, sector))
        await postgres.execute(
            """INSERT INTO employers (id, company_name, uen, sector, size,
               locations, partnership_tier, contact_email)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (uen) DO NOTHING""",
            [eid, name, uen, sector, size, locs, tier, f"hr@{name.lower().replace(' ', '')}.com.sg"],
        )
    counts["employers"] = len(COMPANY_NAMES)

    # ── Trainees ────────────────────────────────────────────────────
    trainee_ids: list[tuple[str, str, str]] = []  # (id, sector, programme_id)
    statuses_pool = ["applied"] * 20 + ["enrolled"] * 30 + ["training"] * 50 + ["completed"] * 60 + ["placed"] * 40
    for i in range(200):
        tid = str(uuid.uuid4())
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        name = f"{first} {last}"
        code = f"T{2026}{i+1:04d}"
        nric = _gen_nric()
        sector = rng.choice(SECTORS)
        status = rng.choice(statuses_pool)
        edu = rng.choice(EDUCATION_LEVELS)
        yexp = rng.randint(0, 15)
        prog_type = rng.choice(PROGRAMME_TYPES)

        # Pick matching programme
        prog_keys = [p[0] for p in programmes if p[2] == prog_type]
        if not prog_keys:
            prog_keys = list(programme_ids.keys())
        prog_key = rng.choice(prog_keys)
        prog_id = programme_ids[prog_key]

        trainee_ids.append((tid, sector, prog_id))

        await postgres.execute(
            """INSERT INTO trainees (id, trainee_code, name, email, phone_masked,
               nric_hash, education_level, field_of_study, years_experience,
               career_goals, preferred_sectors, programme_type, programme_id, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
               ON CONFLICT (trainee_code) DO NOTHING""",
            [
                tid, code, name,
                f"{first.lower().replace(' ', '')}.{last.lower()}@email.com",
                f"****{rng.randint(1000,9999)}",
                _hash(nric),
                edu, f"{sector} Studies", yexp,
                [rng.choice(JOB_TITLES.get(sector, ["General"]))],
                [sector],
                prog_type, prog_id, status,
            ],
        )
    counts["trainees"] = 200

    # ── Job Openings ────────────────────────────────────────────────
    opening_ids: list[tuple[str, str]] = []
    for i in range(80):
        oid = str(uuid.uuid4())
        emp_id, emp_sector = rng.choice(employer_ids)
        titles = JOB_TITLES.get(emp_sector, JOB_TITLES["ICT"])
        title = rng.choice(titles)
        required = rng.sample(["Python", "SQL", "JavaScript", "AWS", "Communication", "Teamwork", "Excel"], k=rng.randint(2, 4))
        preferred = rng.sample(["Docker", "React", "Java", "Leadership", "Agile"], k=rng.randint(1, 3))
        sal_min = rng.randint(2500, 5000)
        sal_max = sal_min + rng.randint(500, 2000)
        status = rng.choice(["open", "open", "open", "filled", "closed"])
        opening_ids.append((oid, emp_sector))
        await postgres.execute(
            """INSERT INTO job_openings (id, employer_id, role_title, description,
               required_skills, preferred_skills, experience_years,
               salary_min, salary_max, work_arrangement, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
            [
                oid, emp_id, title, f"Seeking {title} for our {emp_sector} team.",
                required, preferred, rng.randint(0, 5),
                sal_min, sal_max, rng.choice(WORK_ARRANGEMENTS), status,
            ],
        )
    counts["job_openings"] = 80

    # ── Placements ──────────────────────────────────────────────────
    placed_trainees = [t for t in trainee_ids[:120]]
    for i, (tid, sector, prog_id) in enumerate(placed_trainees):
        plid = str(uuid.uuid4())
        emp_id, _ = rng.choice(employer_ids)
        opening_id = rng.choice(opening_ids)[0] if opening_ids else None
        ptype = rng.choice(["full-time", "full-time", "part-time", "contract"])
        source = rng.choice(["lhub-matched", "lhub-matched", "self-sourced"])
        start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 180))
        salary = rng.randint(2800, 6000)
        status = rng.choice(["pending", "verified", "verified", "verified", "rejected"])
        await postgres.execute(
            """INSERT INTO placements (id, trainee_id, employer_id, opening_id,
               programme_id, placement_type, source, start_date, salary, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            [plid, tid, emp_id, opening_id, prog_id, ptype, source, start, salary, status],
        )
    counts["placements"] = len(placed_trainees)

    logger.info("CareerForge synthetic data seeded: %s", counts)
    return counts
