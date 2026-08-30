# Production Hardening

This build addresses the main POC risks identified during the product review.

## Security

- API-key mode uses a server-side session and constant-time secret comparison.
- CSRF protection covers authenticated state-changing form/API requests.
- Secure HTTP response headers are applied by default.
- Upload size, file-count, filename and extension limits are enforced.
- API and benchmark rate limits are enforced.
- Optional Redis-backed rate limiting is available for multi-instance deployments.
- Source IDs are validated to prevent path traversal.
- Retrieval applies sensitivity, tenant and source/document ACLs before context construction.
- Tool access applies the same retrieval authorization boundary.
- Retrieved documents are explicitly treated as untrusted data in LLM prompts.
- AWS credentials should come from the normal boto3 role/profile chain; static credentials are not required.

## Safe persistence

Local vector and cache state no longer uses pickle. Vector metadata is JSON and vectors are NPZ with `allow_pickle=False`.

Existing legacy `.pkl` indexes are intentionally not loaded. Re-ingest a source to create the safe v2 index.

## Incremental ingestion

Changed documents are removed and re-indexed individually. Remote/semantic embedders can upsert deltas. The local TF-IDF embedder correctly rebuilds because its vocabulary depends on the complete corpus.

## Evaluation

Confidence now exposes:

- retrieval score
- evidence coverage
- claim coverage
- groundedness proxy
- source agreement
- claim-level support diagnostics

Benchmark Studio uses a transparent score based on citation coverage, claim coverage and successful cases. It is explicitly a diagnostic and not a factual correctness guarantee.

Live benchmarks record latency and provider token usage where the provider returns usage data.

## Background jobs

Set:

```text
KF_ASYNC_JOBS=1
```

to move ingestion and benchmark work to the bounded local job manager. Job state is queryable through `/api/jobs`.

For multi-instance production, replace the local job backend with a durable queue/worker implementation before scaling horizontally.

## Authentication

Local default:

```text
KF_AUTH_MODE=none
```

Simple cloud control-plane mode:

```text
KF_AUTH_MODE=api_key
ADMIN_API_KEY=<strong random secret>
SECRET_KEY=<strong random secret>
```

For a real enterprise deployment, put OIDC/SSO in front of the application and map identities/groups to tenant and document ACLs.

## Remaining infrastructure decisions

The application is now hardened for a serious POC/single-instance deployment. A true horizontally scalable enterprise deployment still needs durable shared stores and queue workers:

- S3/object storage
- PostgreSQL or equivalent metadata store
- managed vector/search backend
- SQS or equivalent durable job queue
- ECS/Fargate or another scalable runtime
- OIDC/SSO provider

Those are infrastructure choices, not reasons to fork the local Python product.
