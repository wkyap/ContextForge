# Finance Domain Adapter

Risk management, compliance, transaction monitoring.

## Directory Structure

| Folder | Purpose |
|--------|---------|
| `schema/` | Knowledge SKILL.md files — Entity, Account, Transaction, Instrument, RiskAssessment, Counterparty |
| `ingestion/` | Ingestion SKILL.md files — SWIFT MT/MX, FIX protocol, Bloomberg feeds |
| `tools/` | Computation SKILL.md files — VaR calculation, AML scoring, exposure aggregation |
| `templates/` | Template SKILL.md files — risk reports, regulatory filings, compliance summaries |
| `guardrails/` | Guardrail SKILL.md files — PII/PCI masking, insider-trading boundary checks |
| `channels/` | Channel SKILL.md files — Bloomberg terminal integration, compliance desk alerts |

## Key Entity Types

- **Entity** — legal entities, corporates, individuals (LEI)
- **Account** — trading accounts, custody accounts
- **Transaction** — trades, payments, settlements
- **Instrument** — equities, bonds, derivatives (ISIN / CUSIP)
- **RiskAssessment** — credit scores, AML flags, KYC status
- **Counterparty** — trading counterparties, clearing houses

## Data Sources

- SWIFT message feeds
- Market data providers (Bloomberg, Refinitiv)
- Internal ledger / core banking exports
