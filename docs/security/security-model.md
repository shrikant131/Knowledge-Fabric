# Security model

The POC follows a local-first, evidence-first model.

## Current guarantees

- no external LLM calls when LLM is OFF;
- credentials are referenced through environment variables;
- sensitivity filtering occurs before generation;
- answers expose evidence rather than hiding retrieval provenance.

## Production hardening required

The POC is not an enterprise authorization system. Before exposing confidential data to users, add identity-aware ACL filtering, tenant isolation, audit logging, secure secret storage and security testing.
