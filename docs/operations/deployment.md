# Deployment guide

## Local

Use `start.sh` or `start.bat`.

## Docker

Use `docker compose up --build`.

## Production-shaped deployment

Recommended evolution:

- Flask control plane behind a production WSGI server
- managed PostgreSQL for registry/audit metadata
- OpenSearch or pgvector for retrieval at scale
- object storage for source artifacts
- managed queue/event bus for ingestion
- enterprise identity/SSO
- centralized logs and metrics
- managed secret store

The local implementation is deliberately designed around replaceable interfaces so these changes do not require rewriting the agent contract.
