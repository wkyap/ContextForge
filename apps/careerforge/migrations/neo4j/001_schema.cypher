// ═══════════════════════════════════════════════════════
// CareerForge — Workforce Domain Schema
// Neo4j constraints, indexes, and skill taxonomy setup
// ═══════════════════════════════════════════════════════

// ── Uniqueness Constraints ──────────────────────────────
CREATE CONSTRAINT trainee_id_unique IF NOT EXISTS
FOR (t:Trainee) REQUIRE t.trainee_id IS UNIQUE;

CREATE CONSTRAINT course_id_unique IF NOT EXISTS
FOR (c:Course) REQUIRE c.course_id IS UNIQUE;

CREATE CONSTRAINT employer_id_unique IF NOT EXISTS
FOR (e:Employer) REQUIRE e.employer_id IS UNIQUE;

CREATE CONSTRAINT skill_id_unique IF NOT EXISTS
FOR (s:Skill) REQUIRE s.skill_id IS UNIQUE;

CREATE CONSTRAINT opening_id_unique IF NOT EXISTS
FOR (j:JobOpening) REQUIRE j.opening_id IS UNIQUE;

CREATE CONSTRAINT placement_id_unique IF NOT EXISTS
FOR (p:Placement) REQUIRE p.placement_id IS UNIQUE;

CREATE CONSTRAINT programme_id_unique IF NOT EXISTS
FOR (pr:Programme) REQUIRE pr.programme_id IS UNIQUE;

// ── Performance Indexes ────────────────────────────────
CREATE INDEX trainee_status IF NOT EXISTS FOR (t:Trainee) ON (t.status);
CREATE INDEX trainee_programme IF NOT EXISTS FOR (t:Trainee) ON (t.programme_type);
CREATE INDEX trainee_sector IF NOT EXISTS FOR (t:Trainee) ON (t.preferred_sectors);
CREATE INDEX course_sector IF NOT EXISTS FOR (c:Course) ON (c.sector);
CREATE INDEX course_ssg IF NOT EXISTS FOR (c:Course) ON (c.ssg_course_code);
CREATE INDEX employer_sector IF NOT EXISTS FOR (e:Employer) ON (e.sector);
CREATE INDEX employer_tier IF NOT EXISTS FOR (e:Employer) ON (e.partnership_tier);
CREATE INDEX skill_category IF NOT EXISTS FOR (s:Skill) ON (s.category);
CREATE INDEX skill_ssg IF NOT EXISTS FOR (s:Skill) ON (s.ssg_framework_code);
CREATE INDEX opening_status IF NOT EXISTS FOR (j:JobOpening) ON (j.status);
CREATE INDEX placement_status IF NOT EXISTS FOR (p:Placement) ON (p.status);

// ── Temporal indexes (inherited from Entity base) ───────
CREATE INDEX trainee_current IF NOT EXISTS FOR (t:Trainee) ON (t._is_current);
CREATE INDEX course_current IF NOT EXISTS FOR (c:Course) ON (c._is_current);
CREATE INDEX employer_current IF NOT EXISTS FOR (e:Employer) ON (e._is_current);

// ── Full-text search indexes ────────────────────────────
CREATE FULLTEXT INDEX trainee_search IF NOT EXISTS
FOR (t:Trainee) ON EACH [t.name, t.field_of_study, t.career_goals];

CREATE FULLTEXT INDEX course_search IF NOT EXISTS
FOR (c:Course) ON EACH [c.title, c.skills_taught];

CREATE FULLTEXT INDEX employer_search IF NOT EXISTS
FOR (e:Employer) ON EACH [e.company_name, e.hiring_needs];

CREATE FULLTEXT INDEX skill_search IF NOT EXISTS
FOR (s:Skill) ON EACH [s.name, s.category];

CREATE FULLTEXT INDEX opening_search IF NOT EXISTS
FOR (j:JobOpening) ON EACH [j.role_title, j.description, j.required_skills];
