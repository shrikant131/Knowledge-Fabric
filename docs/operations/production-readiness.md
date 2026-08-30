# Production readiness checklist

Before running multiple application replicas, replace local JSON/index persistence with managed stores and enable identity-aware ACL filtering.

Required hardening:
- OIDC/SSO and RBAC
- Secrets Manager/Key Vault/Secret Manager
- document/source ACL enforcement before retrieval
- S3/Blob/GCS durable originals
- PostgreSQL metadata/config/audit
- managed vector/hybrid search
- queue-backed ingestion/evaluation workers
- distributed tracing and metrics
- backups and disaster recovery
- rate limits and cost budgets
- CI regression gates

The included cloud manifests are deployment starters, not a claim that all of the above enterprise controls are already implemented.
