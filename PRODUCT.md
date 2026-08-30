# Knowledge Fabric Product Baseline

This build includes a local-first Knowledge Fabric, hybrid RAG, agent tools, optional LLM providers, GitHub ingestion, evaluation, and a detailed Admin Control Plane.

## Control plane guarantees

- Configuration changes are persistent.
- Changes are versioned.
- Changes are audited with actor/reason.
- Optimistic concurrency prevents stale overwrites.
- Unknown settings are rejected.
- Secrets are never returned by environment-status APIs.
- Provider readiness is distinct from successful live generation.

## Current production boundary

Authentication/SSO, document-level ACL enforcement, external secrets management, distributed workers, durable multi-user job storage, and production-grade observability still require deployment-specific integration.
