-- ═══════════════════════════════════════════════════════
-- CareerForge — Workforce Domain Tables
-- Career placement programme management
-- ═══════════════════════════════════════════════════════

-- Programmes
CREATE TABLE IF NOT EXISTS programmes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(300) NOT NULL,
    type            VARCHAR(50),
    sector          VARCHAR(50),
    target_placement_rate DECIMAL(5,2),
    reporting_agency VARCHAR(20),
    active          BOOLEAN DEFAULT TRUE,
    neo4j_entity_id VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Trainees
CREATE TABLE IF NOT EXISTS trainees (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trainee_code    VARCHAR(20) UNIQUE NOT NULL,
    name            VARCHAR(200) NOT NULL,
    email           VARCHAR(200),
    phone_masked    VARCHAR(20),
    nric_hash       VARCHAR(64),
    education_level VARCHAR(50),
    field_of_study  VARCHAR(200),
    years_experience INTEGER DEFAULT 0,
    career_goals    JSONB DEFAULT '[]',
    preferred_sectors JSONB DEFAULT '[]',
    preferred_locations JSONB DEFAULT '[]',
    programme_type  VARCHAR(50),
    programme_id    UUID REFERENCES programmes(id),
    status          VARCHAR(30) DEFAULT 'applied',
    neo4j_entity_id VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Courses
CREATE TABLE IF NOT EXISTS courses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_code     VARCHAR(50) UNIQUE NOT NULL,
    title           VARCHAR(300) NOT NULL,
    provider        VARCHAR(200) DEFAULT 'NTUC LearningHub',
    sector          VARCHAR(50),
    duration_weeks  INTEGER,
    mode            VARCHAR(30),
    skills_taught   JSONB DEFAULT '[]',
    prerequisites   JSONB DEFAULT '[]',
    ssg_course_code VARCHAR(50),
    capacity        INTEGER,
    current_enrolment INTEGER DEFAULT 0,
    neo4j_entity_id VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Employers
CREATE TABLE IF NOT EXISTS employers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uen             VARCHAR(20) UNIQUE,
    company_name    VARCHAR(300) NOT NULL,
    sector          VARCHAR(50),
    size            VARCHAR(20),
    locations       JSONB DEFAULT '[]',
    partnership_tier VARCHAR(20) DEFAULT 'new',
    contact_email   VARCHAR(200),
    neo4j_entity_id VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Job openings
CREATE TABLE IF NOT EXISTS job_openings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id     UUID REFERENCES employers(id),
    role_title      VARCHAR(300) NOT NULL,
    description     TEXT,
    required_skills JSONB DEFAULT '[]',
    preferred_skills JSONB DEFAULT '[]',
    experience_years INTEGER DEFAULT 0,
    salary_min      DECIMAL(10,2),
    salary_max      DECIMAL(10,2),
    work_arrangement VARCHAR(30),
    status          VARCHAR(20) DEFAULT 'open',
    posted_at       TIMESTAMPTZ DEFAULT now(),
    neo4j_entity_id VARCHAR(100)
);

-- Applications (trainee enrolment into courses)
CREATE TABLE IF NOT EXISTS applications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trainee_id      UUID REFERENCES trainees(id),
    course_id       UUID REFERENCES courses(id),
    recommended_by  VARCHAR(20) DEFAULT 'ai',
    match_score     DECIMAL(5,2),
    recommendation_reasoning TEXT,
    skills_gap_analysis JSONB,
    status          VARCHAR(30) DEFAULT 'pending',
    reviewed_by     VARCHAR(200),
    review_reason   TEXT,
    proposal_id     UUID REFERENCES proposals(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    reviewed_at     TIMESTAMPTZ
);

-- Placements (employment outcomes)
CREATE TABLE IF NOT EXISTS placements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trainee_id      UUID REFERENCES trainees(id),
    employer_id     UUID REFERENCES employers(id),
    opening_id      UUID REFERENCES job_openings(id),
    programme_id    UUID REFERENCES programmes(id),
    placement_type  VARCHAR(30),
    source          VARCHAR(30),
    start_date      DATE,
    salary          DECIMAL(10,2),
    status          VARCHAR(30) DEFAULT 'pending',
    verified_at     TIMESTAMPTZ,
    verified_by     VARCHAR(200),
    neo4j_entity_id VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Documents (uploaded employment evidence)
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trainee_id      UUID REFERENCES trainees(id),
    placement_id    UUID REFERENCES placements(id),
    document_type   VARCHAR(30),
    file_path       TEXT NOT NULL,
    file_hash       VARCHAR(64),
    ocr_text        TEXT,
    extracted_data  JSONB,
    confidence      DECIMAL(5,4),
    verification_status VARCHAR(20) DEFAULT 'pending',
    auto_approved   BOOLEAN DEFAULT FALSE,
    reviewed_by     VARCHAR(200),
    review_notes    TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    verified_at     TIMESTAMPTZ
);

-- Matching results
CREATE TABLE IF NOT EXISTS matching_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trainee_id      UUID REFERENCES trainees(id),
    target_type     VARCHAR(20),
    target_id       UUID,
    composite_score DECIMAL(5,4),
    skill_coverage  DECIMAL(5,4),
    score_breakdown JSONB,
    explanation     TEXT,
    algorithm_version VARCHAR(20) DEFAULT 'v1',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trainees_status ON trainees(status);
CREATE INDEX IF NOT EXISTS idx_trainees_programme ON trainees(programme_type);
CREATE INDEX IF NOT EXISTS idx_trainees_email ON trainees(email);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_trainee ON applications(trainee_id);
CREATE INDEX IF NOT EXISTS idx_placements_status ON placements(status);
CREATE INDEX IF NOT EXISTS idx_placements_trainee ON placements(trainee_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(verification_status);
CREATE INDEX IF NOT EXISTS idx_documents_trainee ON documents(trainee_id);
CREATE INDEX IF NOT EXISTS idx_matching_trainee ON matching_results(trainee_id);
CREATE INDEX IF NOT EXISTS idx_job_openings_status ON job_openings(status);
CREATE INDEX IF NOT EXISTS idx_job_openings_employer ON job_openings(employer_id);
