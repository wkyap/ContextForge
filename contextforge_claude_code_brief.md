# Claude Code Implementation Brief for ContextForge

This file is a ready-to-use handoff for Claude Code to improve the **ContextForge** repository in a structured way.

Related review file:
- `contextforge_review_recommendations.md`

---

## 1) Role and Objective

You are acting as a senior software architect and hands-on implementation engineer for the GitHub repository **ContextForge**.

Your goal is to improve the repository based on the architectural review and recommendations already prepared. Focus on making the repo:

- clearer in positioning
- easier to run
- more internally consistent
- safer by default
- more credible as a platform
- easier for contributors to extend

Do not make random cosmetic edits. Prioritize improvements that increase:
- clarity
- reliability
- maintainability
- developer onboarding
- product trust

---

## 2) High-Level Assessment to Act On

The repository has strong ideas:
- AI-native context engineering platform
- skill-based domain adapters
- multi-agent orchestration
- governance mindset
- compound AI stack

But it currently has several gaps:
- platform story and domain app story are mixed
- documentation and implementation maturity are not fully aligned
- deployment footprint is too heavy for quick evaluation
- runtime behavior needs stronger consistency and hardening
- some defaults are too development-oriented
- frontend truthfulness to backend state should improve

Your job is to systematically reduce those gaps.

---

## 3) Working Rules

Please follow these rules carefully:

1. **Work in small, reviewable commits**
   - Group related changes together.
   - Prefer multiple focused commits over one giant commit.

2. **Do not break existing core flows**
   - Preserve current architecture direction unless there is a very strong reason to change it.

3. **Prefer high-value fixes**
   - README clarity beats adding new speculative features.
   - Safer defaults beat new dashboards.
   - Better runtime consistency beats broader scope.

4. **Mark maturity honestly**
   - If something is partial, label it partial.
   - Do not present roadmap items as fully implemented.

5. **Do not over-engineer**
   - This repo needs focus and credibility more than extra layers.

6. **When uncertain, choose explicitness**
   - Better docs
   - better comments
   - better naming
   - better status signaling

---

## 4) Priority Order

Implement in this order unless blocked.

### Priority 1 — Clarify product positioning and repository narrative
Goal: make the repo understandable in under 2 minutes.

Tasks:
- Rewrite the top-level `README.md`
- Clearly distinguish:
  - **ContextForge** = platform
  - **CareerForge** = example/reference domain application built on it
- Add a **Current Status** section
- Add an **Implemented / Partial / Planned** section
- Add a **Repository Structure** section that matches reality
- Remove or reword any statements that overclaim maturity
- Add a short **Quick Evaluation Path** for new users

Expected output:
- A cleaner README that tells a coherent story
- No confusion between platform vs domain app
- More realistic and trustworthy positioning

---

### Priority 2 — Fix documentation consistency
Goal: remove mismatch between README, docs, code structure, and current repo reality.

Tasks:
- Review all docs referenced in README
- Ensure referenced docs actually exist
- If missing, create minimal but useful versions of:
  - `docs/architecture.md`
  - `docs/deployment-guide.md`
  - `docs/api-reference.md`
  - `docs/contributing.md`
  - `docs/maturity-model.md`
- Standardize layer numbering and terminology across docs
- Use one canonical architecture description
- Add a **component maturity matrix** with statuses such as:
  - stable
  - beta
  - experimental
  - planned

Expected output:
- Docs are present and aligned
- No dead links or aspirational placeholders pretending to be complete
- Consistent terminology everywhere

---

### Priority 3 — Reduce deployment friction
Goal: make the project easier to try locally.

Tasks:
- Keep current full-stack compose setup, but add a lighter evaluation path
- Create smaller compose options such as:
  - `docker-compose.minimal.yml`
  - `docker-compose.observability.yml`
  - `docker-compose.full.yml`
  or an equivalent profile-based structure if cleaner
- Ensure minimal setup can demonstrate a meaningful workflow
- Document what each deployment mode includes
- Add a “fastest way to try this repo” section
- Prefer a minimum viable stack for first-time users

Suggested minimal stack:
- API
- frontend
- Postgres
- Redis
- Qdrant

Optional layers:
- Neo4j
- Langfuse + ClickHouse
- Keycloak
- Ollama
- TimescaleDB

Expected output:
- Quicker onboarding
- Clear deployment tiers
- Lower barrier to evaluation

---

### Priority 4 — Improve security and environment hygiene
Goal: make defaults safer and less misleading.

Tasks:
- Review `.env.example` and environment handling
- Add prominent warnings for insecure development defaults
- Separate development and production expectations in docs
- Ensure default behavior does not silently look “production-ready” when it is not
- Add startup validation or warnings for:
  - default passwords
  - auth disabled in non-dev contexts
  - insecure public exposure assumptions
- Remove obviously dangerous ambiguity where possible

Expected output:
- Safer repo defaults
- Less risk of accidental insecure deployment
- More enterprise credibility

---

### Priority 5 — Harden runtime consistency
Goal: reduce semantic drift and fragile behavior inside the agent system.

Tasks:
- Review budget enforcement logic
- Move hardcoded limits into config or policy where appropriate
- Standardize guardrail outcome states
  - for example: `pass`, `rewrite`, `review`, `block`
- Make routing logic match emitted statuses exactly
- Review template execution flow
- Replace naive string substitution with something safer if feasible
  - or at minimum document limitations clearly
- Improve session/history handling contracts between backend and frontend
- Ensure response formatting is more robust and less coupled to internal assumptions

Expected output:
- Cleaner runtime semantics
- Better alignment between graph logic and guardrail outputs
- Less brittle agent behavior

---

### Priority 6 — Improve frontend truthfulness and product coherence
Goal: make the UI better reflect what the backend actually supports.

Tasks:
- Review frontend branding and navigation
- Make platform mode vs domain app mode clearer
- Improve session resume behavior
- If prior turns are persisted, expose a better user-facing history experience
- Add visibility where possible for:
  - domain in use
  - run status
  - usage/tokens/cost
  - provenance/sources
  - governance or review state
- Avoid fake completeness; show honest partial states where needed

Expected output:
- UI feels more trustworthy
- Less confusion
- Better alignment with backend capabilities

---

## 5) Specific Code/Architecture Review Themes

Please inspect and improve these areas carefully.

### A. Naming and consistency
Check for:
- mixed platform/domain naming
- inconsistent route naming
- inconsistent docs naming
- inconsistent architecture layer numbering

### B. Runtime configuration
Check for:
- hardcoded budget values
- duplicated config logic
- settings that should be env-driven but are local constants

### C. Guardrail pipeline
Check for:
- mismatch between produced statuses and router expectations
- ambiguous error/rewrite/review semantics
- missing test coverage

### D. Template execution
Check for:
- naive variable replacement
- lack of escaping or validation
- weak safety posture
- unclear template behavior

### E. Session UX
Check for:
- persisted backend session state not properly represented in UI
- incomplete resume behavior
- misleading user messaging

### F. Docs credibility
Check for:
- claims not supported by implementation
- roadmap features presented as done
- missing docs linked in README

---

## 6) Deliverables Required

Please produce these deliverables in the repository:

1. **Updated README**
2. **Improved docs folder**
3. **Simplified local deployment path**
4. **Environment/security guidance improvements**
5. **Runtime consistency fixes**
6. **Any necessary tests for the above**
7. **A final CHANGELOG-style summary** in a markdown file

Create:
- `docs/implementation-summary.md`

That summary should include:
- what was changed
- why it was changed
- what is still incomplete
- what should be done next

---

## 7) Suggested Implementation Plan

Use this order of execution:

### Phase 1 — Repository narrative
- README rewrite
- docs cleanup
- maturity matrix
- architecture consistency

### Phase 2 — DevEx and deployment
- lighter compose setup
- onboarding flow
- env guidance
- security notes

### Phase 3 — Runtime hardening
- config cleanup
- guardrail state alignment
- budget logic cleanup
- template safety improvements

### Phase 4 — Frontend honesty and UX
- session/history improvements
- brand clarity
- state visibility improvements

### Phase 5 — Final polish
- tests
- documentation sync
- implementation summary
- cleanup of stale wording/comments

---

## 8) Acceptance Criteria

The work is complete only when these are true:

- A new contributor can understand the repo quickly
- Platform vs domain-app distinction is clear
- README does not overclaim
- Missing referenced docs are resolved
- There is a lower-friction local run path
- Security/development defaults are more explicit
- Guardrail/runtime semantics are more consistent
- Frontend messaging is more truthful about persisted sessions/state
- A summary file explains all changes clearly

---

## 9) Output Style Required From You

When executing, please provide:
- concise progress updates
- clear reasoning for major structural changes
- exact file changes
- note any assumptions
- do not silently remove major functionality without explanation

If a recommendation cannot be implemented cleanly right now, document it under:
- **Deferred**
- **Reason**
- **Recommended next step**

---

## 10) Optional Nice-to-Haves

If time permits and it fits naturally, also consider:

- add ADRs under `docs/adr/`
- add a simple benchmark/status page
- add architecture diagrams
- add a “first successful demo” walkthrough
- add feature maturity badges or tables
- add failure-mode documentation

Do these only after the higher-priority work is complete.

---

## 11) Final Instruction

Start by:
1. auditing the repo against this brief,
2. proposing a concrete change plan,
3. then implementing the highest-value improvements first.

Be pragmatic, honest, and selective.
The goal is not to make the repo look bigger.
The goal is to make it **clearer, tighter, and more credible**.
