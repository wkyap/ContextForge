# ContextForge Engine x CareerForge — Solution Architecture

**Document:** Solution Architecture Diagram
**Date:** 2026-03-31

---

## 1. High-Level Architecture

```
                           ┌─────────────────────────────────────────────────┐
                           │              CAREERFORGE APP                    │
                           │       (Domain-Specific Presentation)           │
                           │                                                 │
                           │  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
                           │  │Coordinator│ │ Trainee  │ │   Employer    │  │
                           │  │ Dashboard │ │  Portal  │ │    Portal     │  │
                           │  └─────┬─────┘ └────┬─────┘ └──────┬────────┘  │
                           │        │            │               │           │
                           │  ┌─────┴────┐ ┌────┴──────┐ ┌─────┴─────────┐ │
                           │  │Enrolment │ │ Matching  │ │  Compliance   │ │
                           │  │  Review  │ │ Interface │ │  Dashboard    │ │
                           │  └─────┬────┘ └────┬──────┘ └─────┬─────────┘ │
                           └────────┼────────────┼─────────────┼───────────┘
                                    │            │             │
                                    ▼            ▼             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXTFORGE ENGINE v3.0                             │
│                  (Sector-Agnostic AI Context Platform)                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 8: PRESENTATION                               │  │
│  │                                                                        │  │
│  │   React 18 + Vite + Tailwind + Zustand + React Query                  │  │
│  │   ┌────────────┐  ┌──────────────┐  ┌──────────────┐                  │  │
│  │   │ AgentChat  │  │  KG Explorer │  │  Admin Panel │                  │  │
│  │   │  (Reused)  │  │   (Reused)   │  │   (Reused)   │                  │  │
│  │   └────────────┘  └──────────────┘  └──────────────┘                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 7: API GATEWAY                                │  │
│  │                                                                        │  │
│  │   FastAPI + CORS + JWT Auth (Keycloak)                                │  │
│  │                                                                        │  │
│  │   ┌─── Engine Routes (Reused) ──┐  ┌── CareerForge Routes (New) ───┐ │  │
│  │   │ /health  /skills  /graph    │  │ /trainees    /courses         │ │  │
│  │   │ /search  /agents  /admin    │  │ /employers   /openings        │ │  │
│  │   │ /governance  /pipelines     │  │ /placements  /reports         │ │  │
│  │   │ /timeseries  /onboarding    │  │ /documents   /applications    │ │  │
│  │   │ /ws (WebSocket streaming)   │  │                               │ │  │
│  │   └─────────────────────────────┘  └───────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 6: GUARDRAILS                                 │  │
│  │                                                                        │  │
│  │   ┌──────────────────┐  ┌────────────────┐  ┌──────────────────────┐ │  │
│  │   │  PDPA Compliance │  │  Hallucination │  │  Provenance Tracker  │ │  │
│  │   │  (Extended)      │  │  Checker       │  │  (Reused)            │ │  │
│  │   │                  │  │  (Reused)      │  │                      │ │  │
│  │   │  - NRIC masking  │  │                │  │  Source attribution  │ │  │
│  │   │  - SG phone mask │  │                │  │  for all AI outputs  │ │  │
│  │   │  - Email redact  │  │                │  │                      │ │  │
│  │   │  - NRIC hashing  │  │                │  │                      │ │  │
│  │   └──────────────────┘  └────────────────┘  └──────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 5: AGENT ORCHESTRATION                        │  │
│  │                                                                        │  │
│  │   LangGraph StateGraph + PydanticAI Agents                            │  │
│  │                                                                        │  │
│  │   ┌─── Engine Agents (Reused) ──┐  ┌── CareerForge Agents (New) ───┐ │  │
│  │   │                             │  │                                │ │  │
│  │   │  Orchestrator (Router)      │  │  Enrolment Agent              │ │  │
│  │   │  Retrieval Agent            │  │  - Course recommendation      │ │  │
│  │   │  Analysis Agent             │  │  - Skills gap analysis        │ │  │
│  │   │  Action Agent               │  │  - Intake assessment          │ │  │
│  │   │                             │  │                                │ │  │
│  │   │  Budget Controller          │  │  Matching Agent               │ │  │
│  │   │  Error Recovery             │  │  - Trainee ↔ Job scoring      │ │  │
│  │   │  Memory Manager             │  │  - KG + Vector hybrid search  │ │  │
│  │   │  Model Router               │  │  - Composite scoring (40/25/  │ │  │
│  │   │                             │  │    20/15 formula)             │ │  │
│  │   │  Context Engine (6-stage):  │  │                                │ │  │
│  │   │  classify → retrieve →      │  │  Verification Agent           │ │  │
│  │   │  prune → compose →          │  │  - Document OCR + extraction  │ │  │
│  │   │  compress → cache           │  │  - Confidence scoring         │ │  │
│  │   │                             │  │  - Auto/manual approve flow   │ │  │
│  │   │  Human Review Node          │  │                                │ │  │
│  │   │  Guardrails Node            │  │  Reporting Agent              │ │  │
│  │   │                             │  │  - SSG compliance reports     │ │  │
│  │   │                             │  │  - Placement rate analytics   │ │  │
│  │   │                             │  │  - At-risk trainee detection  │ │  │
│  │   └─────────────────────────────┘  └────────────────────────────────┘ │  │
│  │                                                                        │  │
│  │   Autonomy Controller (L0-L4):                                        │  │
│  │   L1: course_recommendation, placement_matching, ssg_report           │  │
│  │   L2: reminder_scheduling, skills_gap_analysis, document_verification │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 4: DOMAIN ADAPTER                             │  │
│  │                                                                        │  │
│  │   domains/workforce/ (SKILL.md Files)                                 │  │
│  │                                                                        │  │
│  │   ┌── Schema ──────────┐  ┌── Tools ──────────────┐                   │  │
│  │   │ trainee.md         │  │ matching_scorer.md     │                   │  │
│  │   │ course.md          │  │ skills_gap_analyzer.md │                   │  │
│  │   │ employer.md        │  │ ssg_report_generator.md│                   │  │
│  │   │ skill.md           │  └────────────────────────┘                   │  │
│  │   │ placement.md       │                                               │  │
│  │   │ job_opening.md     │  ┌── Ingestion ──────────┐                   │  │
│  │   └────────────────────┘  │ excel_import.md        │                   │  │
│  │                            │ document_ocr.md        │                   │  │
│  │   ┌── Guardrails ──────┐  └────────────────────────┘                   │  │
│  │   │ pdpa_nric.md       │                                               │  │
│  │   └────────────────────┘  SkillRegistry parses YAML frontmatter +     │  │
│  │                            markdown body at startup                     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 3: KNOWLEDGE FOUNDATION                       │  │
│  │                                                                        │  │
│  │   ┌── Neo4j Temporal KG ───────────────────────────────────────────┐  │  │
│  │   │                                                                 │  │  │
│  │   │  (Trainee)──[:HAS_SKILL]──>(Skill)<──[:TEACHES]──(Course)     │  │  │
│  │   │      │                        │                      │         │  │  │
│  │   │      ├──[:ENROLLED_IN]────────┼──────────────────────┘         │  │  │
│  │   │      ├──[:APPLIED_TO]──>(JobOpening)<──[:POSTED]──(Employer)   │  │  │
│  │   │      ├──[:PLACED_AT]──>(Employer)                              │  │  │
│  │   │      ├──[:IN_PROGRAMME]──>(Programme)                          │  │  │
│  │   │      └──[:SUBMITTED]──>(Document)                              │  │  │
│  │   │                                                                 │  │  │
│  │   │  Versioning: _is_current, _valid_from, _valid_to, _version    │  │  │
│  │   │  Full-text: trainee_search, course_search, employer_search    │  │  │
│  │   │  SSG Taxonomy: (Skill)──[:PARENT_OF]──>(Skill)                │  │  │
│  │   └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │   ┌── Qdrant Vector DB ────────────────────────────────────────────┐  │  │
│  │   │  documents collection  — CV/resume embeddings                  │  │  │
│  │   │  entities collection   — trainee/employer profile embeddings   │  │  │
│  │   │  skills collection     — skill description embeddings          │  │  │
│  │   │  communities collection — cluster embeddings                   │  │  │
│  │   │                                                                 │  │  │
│  │   │  Model: text-embedding-3-small (1536-dim) via LiteLLM         │  │  │
│  │   └─────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 2: DATA FOUNDATION                            │  │
│  │                                                                        │  │
│  │   ┌── PostgreSQL 16 ───────────┐  ┌── TimescaleDB ─────────────────┐ │  │
│  │   │                             │  │                                 │ │  │
│  │   │  Engine tables (reused):    │  │  trainee_metrics hypertable    │ │  │
│  │   │  - skills, sessions         │  │  (trainee_id, programme_id,    │ │  │
│  │   │  - proposals, audit_log     │  │   metric_name, metric_value,   │ │  │
│  │   │  - autonomy_levels          │  │   recorded_at)                 │ │  │
│  │   │  - pipelines                │  │                                 │ │  │
│  │   │                             │  │  Continuous aggregates:         │ │  │
│  │   │  CareerForge tables (new):  │  │  weekly_trainee_metrics        │ │  │
│  │   │  - programmes               │  │                                 │ │  │
│  │   │  - trainees                 │  │  Retention: 730 days           │ │  │
│  │   │  - courses                  │  └─────────────────────────────────┘ │  │
│  │   │  - employers                │                                      │  │
│  │   │  - job_openings             │  ┌── Redis 7 ─────────────────────┐ │  │
│  │   │  - applications             │  │  Session cache                  │ │  │
│  │   │  - placements               │  │  Context window cache           │ │  │
│  │   │  - documents                │  │  Real-time notifications        │ │  │
│  │   │  - matching_results         │  │  Pub/Sub event streams          │ │  │
│  │   │                             │  └─────────────────────────────────┘ │  │
│  │   └─────────────────────────────┘                                      │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 1: INFRASTRUCTURE                             │  │
│  │                                                                        │  │
│  │   Docker Compose (contextforge-net bridge network)                    │  │
│  │                                                                        │  │
│  │   ┌─────────┐ ┌───────────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ │  │
│  │   │Postgres │ │TimescaleDB│ │ Neo4j │ │Qdrant │ │ Redis │ │LiteLLM│ │  │
│  │   │  :5432  │ │   :5433   │ │ :7687 │ │ :6333 │ │ :6379 │ │ :4000 │ │  │
│  │   └─────────┘ └───────────┘ └───────┘ └───────┘ └───────┘ └───────┘ │  │
│  │                                                                        │  │
│  │   ┌── Optional Profiles ──────────────────────────────────────────┐   │  │
│  │   │  observability: ClickHouse + Langfuse (:3001)                 │   │  │
│  │   │  auth:          Keycloak (:8180)                              │   │  │
│  │   │  local-llm:     Ollama (:11434)                               │   │  │
│  │   └───────────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │  EXTERNAL SERVICES   │
                         │                      │
                         │  LiteLLM Gateway     │
                         │  ├─ OpenAI API       │
                         │  ├─ Anthropic API    │
                         │  ├─ Google AI API    │
                         │  └─ Ollama (local)   │
                         │                      │
                         │  Langfuse (traces)   │
                         │  Keycloak (auth)     │
                         │  WhatsApp/Slack/     │
                         │  Teams (channels)    │
                         └─────────────────────┘
```

---

## 2. Data Flow Diagrams

### 2.1 Trainee Enrolment Flow

```
Trainee/Coordinator                  CareerForge API              ContextForge Engine
       │                                   │                              │
       │  POST /trainees                   │                              │
       ├──────────────────────────────────>│                              │
       │                                   │  PDPA Guardrail             │
       │                                   │  (mask NRIC, phone)         │
       │                                   ├─────────────────────────────>│
       │                                   │                              │  Write Postgres
       │                                   │                              │  (trainees table)
       │                                   │                              │
       │                                   │                              │  Write Neo4j
       │                                   │                              │  (:Trainee node +
       │                                   │                              │   :HAS_SKILL edges)
       │                                   │                              │
       │                                   │  Trigger Enrolment Agent    │
       │                                   ├─────────────────────────────>│
       │                                   │                              │  6-Stage Context:
       │                                   │                              │  1. Classify intent
       │                                   │                              │  2. Retrieve KG data
       │                                   │                              │  3. Prune irrelevant
       │                                   │                              │  4. Compose context
       │                                   │                              │  5. Compress tokens
       │                                   │                              │  6. Cache result
       │                                   │                              │
       │                                   │                              │  PydanticAI → LiteLLM
       │                                   │                              │  → Claude/GPT
       │                                   │                              │
       │                                   │  EnrolmentAssessment        │
       │                                   │<─────────────────────────────│
       │                                   │                              │
       │                                   │  Autonomy L1 → Queue        │
       │                                   │  for human approval          │
       │                                   │                              │
       │  Course recommendations           │                              │
       │  (pending coordinator approval)   │                              │
       │<──────────────────────────────────│                              │
```

### 2.2 Placement Matching Flow

```
Coordinator                          CareerForge API              ContextForge Engine
       │                                   │                              │
       │  GET /openings/{id}/matches       │                              │
       ├──────────────────────────────────>│                              │
       │                                   │  Matching Agent trigger     │
       │                                   ├─────────────────────────────>│
       │                                   │                              │
       │                                   │        ┌─────────────────┐  │
       │                                   │        │  Neo4j KG Query │  │
       │                                   │        │  (skills graph  │  │
       │                                   │        │   traversal)    │  │
       │                                   │        └────────┬────────┘  │
       │                                   │                 │           │
       │                                   │        ┌────────▼────────┐  │
       │                                   │        │  Qdrant Vector  │  │
       │                                   │        │  (CV/JD cosine  │  │
       │                                   │        │   similarity)   │  │
       │                                   │        └────────┬────────┘  │
       │                                   │                 │           │
       │                                   │        ┌────────▼────────┐  │
       │                                   │        │ Composite Score │  │
       │                                   │        │ Skills:     40% │  │
       │                                   │        │ Experience: 25% │  │
       │                                   │        │ Quals:      20% │  │
       │                                   │        │ Practical:  15% │  │
       │                                   │        └────────┬────────┘  │
       │                                   │                 │           │
       │                                   │  Ranked matches + explain  │
       │                                   │<─────────────────────────────│
       │                                   │                              │
       │  Ranked candidate list            │  Store in matching_results  │
       │  with AI explanations             │  (Postgres cache)           │
       │<──────────────────────────────────│                              │
```

### 2.3 SSG Compliance Reporting Flow

```
Coordinator                          CareerForge API              ContextForge Engine
       │                                   │                              │
       │  POST /reports/ssg                │                              │
       ├──────────────────────────────────>│                              │
       │                                   │  Reporting Agent trigger    │
       │                                   ├─────────────────────────────>│
       │                                   │                              │
       │                                   │  Query Postgres (programmes,│
       │                                   │  trainees, placements)      │
       │                                   │                              │
       │                                   │  Query TimescaleDB          │
       │                                   │  (weekly aggregates)        │
       │                                   │                              │
       │                                   │  Query Neo4j (placement     │
       │                                   │  graph traversal)           │
       │                                   │                              │
       │                                   │  Autonomy L1 → Always      │
       │                                   │  requires human sign-off    │
       │                                   │                              │
       │  Report data (JSON)               │                              │
       │  + "requires_signoff: true"       │                              │
       │<──────────────────────────────────│                              │
       │                                   │                              │
       │  (Sprint 4: Excel export)         │                              │
```

---

## 3. Component Reuse Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ENGINE REUSE BREAKDOWN                         │
│                                                                     │
│  ██████████████████████████████████████  REUSED AS-IS (60%)        │
│  ░░░░░░░░░░░░░░░░░░                    EXTENDED (25%)              │
│  ▓▓▓▓▓▓▓▓▓▓                            NEW (15%)                  │
│                                                                     │
│  Layer               Reuse    Extend    New                        │
│  ─────────────────   ──────   ──────   ──────                      │
│  Infrastructure      100%       0%       0%    Docker, all DBs     │
│  Data Foundation      70%      30%       0%    +9 Postgres tables  │
│  Knowledge Found.     60%      30%      10%    +workforce KG schema│
│  Domain Adapter        0%       0%     100%    13 new SKILL.md     │
│  Agent Orchestration  50%      20%      30%    +4 career agents    │
│  Guardrails           70%      30%       0%    +PDPA SG extension  │
│  API Gateway          60%       0%      40%    +7 route modules    │
│  Presentation         40%       0%      60%    +6 career pages     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Deployment Topology

```
                    ┌──────────────────────────────────┐
                    │        Docker Host (Dev)          │
                    │                                    │
                    │  docker compose up -d              │
                    │                                    │
                    │  ┌──────────────────────────────┐ │
                    │  │    contextforge-net (bridge)  │ │
                    │  │                                │ │
                    │  │  ┌─────────┐  ┌───────────┐  │ │
                    │  │  │ Postgres│  │TimescaleDB│  │ │
                    │  │  │  :5432  │  │   :5433   │  │ │
                    │  │  └─────────┘  └───────────┘  │ │
                    │  │                                │ │
                    │  │  ┌───────┐  ┌───────┐         │ │
                    │  │  │ Neo4j │  │Qdrant │         │ │
                    │  │  │ :7687 │  │ :6333 │         │ │
                    │  │  └───────┘  └───────┘         │ │
                    │  │                                │ │
                    │  │  ┌───────┐  ┌───────┐         │ │
                    │  │  │ Redis │  │LiteLLM│         │ │
                    │  │  │ :6379 │  │ :4000 │         │ │
                    │  │  └───────┘  └───────┘         │ │
                    │  │                                │ │
                    │  │  ┌──────────────────────────┐ │ │
                    │  │  │   ContextForge API       │ │ │
                    │  │  │   (FastAPI :8000)        │ │ │
                    │  │  │                          │ │ │
                    │  │  │   Engine Routes (v1)     │ │ │
                    │  │  │   + CareerForge Routes   │ │ │
                    │  │  │   + LangGraph Agents     │ │ │
                    │  │  │   + SKILL.md Registry    │ │ │
                    │  │  └──────────────────────────┘ │ │
                    │  │                                │ │
                    │  │  ┌──────────────────────────┐ │ │
                    │  │  │   Frontend (React :3000) │ │ │
                    │  │  │                          │ │ │
                    │  │  │   Engine Pages (reused)  │ │ │
                    │  │  │   + CareerForge Pages    │ │ │
                    │  │  └──────────────────────────┘ │ │
                    │  │                                │ │
                    │  └──────────────────────────────┘ │
                    └──────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ OpenAI   │  │Anthropic │  │ Google   │
              │ API      │  │ API      │  │ AI API   │
              └──────────┘  └──────────┘  └──────────┘
```

---

## 5. Key Design Principle: Domain Adapter Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ContextForge Engine is SECTOR-AGNOSTIC.                      │
│   CareerForge is a DOMAIN ADAPTER that plugs into it.          │
│                                                                 │
│   The adapter pattern means:                                   │
│                                                                 │
│   1. SKILL.md files define the domain vocabulary               │
│      (entities, rules, tools, guardrails)                      │
│                                                                 │
│   2. Database migrations extend the schema                     │
│      (workforce tables, KG constraints, hypertables)           │
│                                                                 │
│   3. PydanticAI agents implement domain logic                  │
│      (enrolment, matching, verification, reporting)            │
│                                                                 │
│   4. API routes expose domain operations                       │
│      (CRUD + domain-specific workflows)                        │
│                                                                 │
│   5. Frontend pages provide domain UI                          │
│      (dashboards, portals, review screens)                     │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                                                         │  │
│   │   domains/                                              │  │
│   │   └── workforce/          ← CareerForge adapter         │  │
│   │       ├── schema/         ← Entity definitions          │  │
│   │       ├── tools/          ← Scoring & analysis rules    │  │
│   │       ├── ingestion/      ← Data import specs           │  │
│   │       └── guardrails/     ← PDPA compliance rules       │  │
│   │                                                         │  │
│   │   Future adapters could include:                        │  │
│   │   └── healthcare/         ← Clinic management           │  │
│   │   └── legal/              ← Case management             │  │
│   │   └── education/          ← Student lifecycle           │  │
│   │                                                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Technology Stack Summary

| Layer | Technology | Purpose | Port |
|---|---|---|---|
| Infrastructure | Docker Compose | Container orchestration | — |
| RDBMS | PostgreSQL 16 | App state, LangGraph checkpoints | 5432 |
| Time Series | TimescaleDB (PG16) | Trainee metrics, continuous aggregates | 5433 |
| Knowledge Graph | Neo4j 5.23 Community | Temporal KG, skill taxonomy, relationship traversal | 7687 |
| Vector DB | Qdrant 1.13.2 | CV/JD embeddings, semantic skill search | 6333 |
| Cache/PubSub | Redis 7.4 | Session cache, notifications, event streams | 6379 |
| LLM Gateway | LiteLLM | Multi-provider routing (OpenAI, Anthropic, Google, Ollama) | 4000 |
| API | FastAPI (Python 3.12) | REST + WebSocket, async | 8000 |
| Agents | LangGraph + PydanticAI | Multi-agent orchestration with structured outputs | — |
| Frontend | React 18 + Vite + Tailwind | SPA with Zustand state + React Query | 3000 |
| Auth | Keycloak 25 | OIDC/JWT RBAC (optional profile) | 8180 |
| Observability | Langfuse 3 + ClickHouse | LLM tracing, cost tracking (optional profile) | 3001 |
| Domain Config | SKILL.md (YAML+MD) | Declarative domain adapter files | — |
