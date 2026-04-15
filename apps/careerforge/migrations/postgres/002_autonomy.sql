-- ═══════════════════════════════════════════════════════
-- CareerForge — Autonomy Level Configuration
-- Graduated AI autonomy (L0-L4) for domain functions
-- ═══════════════════════════════════════════════════════

INSERT INTO autonomy_levels (function_name, autonomy_level)
VALUES
    ('course_recommendation', 1),
    ('document_verification', 1),
    ('placement_matching', 1),
    ('ssg_report_generation', 1),
    ('reminder_scheduling', 2),
    ('skills_gap_analysis', 2)
ON CONFLICT (function_name) DO UPDATE SET
    autonomy_level = EXCLUDED.autonomy_level;
