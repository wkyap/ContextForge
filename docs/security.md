# Security Architecture

## Authentication & Authorization

- **Identity Provider:** Keycloak (OpenID Connect / OAuth 2.0)
- **Token Format:** JWT with RS256 signing
- **JWKS Endpoint:** Auto-discovered from Keycloak issuer URL
- **Roles:** admin, operator, viewer (realm-level)
- **Dev Mode:** Auth bypass via `CONTEXTFORGE_AUTH_DISABLED=true` (default in development)

## API Security

- All API endpoints require a valid JWT bearer token (except health check)
- CORS configured to restrict origins in production
- Request validation via Pydantic models
- Global exception handler prevents stack trace leakage

## Data Protection

### PII / PHI Detection
- Regex-based PII detector scans for: email, phone, NHS numbers, SSN, credit cards, MRN, DOB patterns
- `redact_pii()` function available for output sanitization
- Applied to agent responses before delivery

### Encryption
- All database connections use TLS in production
- Redis connections use password authentication
- Neo4j connections use bolt+s:// in production
- Qdrant API key authentication when deployed

## LLM Security

### Prompt Injection
- System prompts are separated from user input
- Tool calls are validated against allowed tool definitions
- Agent budget limits prevent runaway execution

### Hallucination Prevention
- LLM-based hallucination checker validates responses against source context
- Provenance tracking records which sources informed each response
- Confidence scores propagated from entity extraction to final output

### Cost Controls
- Per-run token budget (default: 100,000 tokens)
- Per-run cost budget (default: $5.00 USD)
- Maximum iterations and tool calls per agent run
- All LLM calls routed through LiteLLM with Langfuse cost tracking

## Governance

### Autonomy Levels (0-4)
- Level 0: All AI actions require human approval
- Level 1: AI proposes, human reviews before execution
- Level 2: AI executes, human notified after
- Level 3: AI autonomous with random spot checks
- Level 4: Full autonomy

### Audit Trail
- Every governance decision logged with: user, action, resource, result, reason
- Correlation IDs link audit entries to Langfuse traces
- Immutable audit log (append-only, no deletes)

## Infrastructure Security

### Docker Compose
- Services communicate over isolated Docker network
- Database passwords configurable via environment variables
- Default passwords in `.env.example` are for development only
- Production deployments should use secrets management (Vault, AWS Secrets Manager)

### Network Segmentation
- Frontend (port 5173) → API only via reverse proxy
- API (port 8000) → Database services on internal network
- Databases not exposed to host in production profiles

## Security Checklist

- [ ] Change all default passwords before production deployment
- [ ] Enable TLS for all database connections
- [ ] Configure CORS with specific allowed origins
- [ ] Set `CONTEXTFORGE_AUTH_DISABLED=false` in production
- [ ] Enable Keycloak brute force protection
- [ ] Set up secrets management for credentials
- [ ] Review PII detection patterns for your domain
- [ ] Configure audit log retention policy
- [ ] Enable rate limiting on API endpoints
- [ ] Set up monitoring alerts for budget exceeded events
