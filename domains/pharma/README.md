# Pharma / Life Sciences Domain Adapter

Drug discovery, clinical trials, regulatory intelligence.

## Directory Structure

| Folder | Purpose |
|--------|---------|
| `schema/` | Knowledge SKILL.md files — Compound, Target, Pathway, Trial, AdverseEvent, Publication |
| `ingestion/` | Ingestion SKILL.md files — PubMed, ClinicalTrials.gov, FDA FAERS |
| `tools/` | Computation SKILL.md files — target-disease association scoring, AE signal detection |
| `templates/` | Template SKILL.md files — literature review summaries, regulatory briefing docs |
| `guardrails/` | Guardrail SKILL.md files — citation verification, off-label claim detection |
| `channels/` | Channel SKILL.md files — Slack integration for research teams |

## Key Entity Types

- **Compound** — small molecules, biologics (ChEMBL ID)
- **Target** — proteins, genes (UniProt / HGNC)
- **Pathway** — biological pathways (Reactome / KEGG)
- **Trial** — clinical studies (NCT numbers)
- **AdverseEvent** — reported safety signals (MedDRA coded)
- **Publication** — journal articles (PubMed ID / DOI)

## Data Sources

- PubMed / Europe PMC APIs
- ClinicalTrials.gov API
- FDA FAERS / EudraVigilance exports
- ChEMBL / UniProt databases
