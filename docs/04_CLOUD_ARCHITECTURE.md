# Knowledge Fabric Cloud Architecture

## Deployment modes

Knowledge Fabric intentionally supports two deployment modes.

### Local

```text
Python
 |
Web/API
 |
Local data/indexes
 |
Optional LLM
```

No Docker is required.

### Cloud POC

```text
HTTPS
 |
EC2
 |
Knowledge Fabric
 |
Bedrock
```

### Production target

```text
                 HTTPS / ALB
                      |
                API/Web Service
                      |
             +--------+--------+
             |                 |
          Database          Queue
             |                 |
             |              Workers
             |                 |
             +--------+--------+
                      |
             +--------+--------+
             |        |        |
             S3   Search/Vector Bedrock
```

## Storage abstraction

The application should hide storage implementation details behind interfaces.

Local:

- filesystem
- local index

Cloud:

- S3
- relational metadata store
- managed search/vector backend

This keeps the user-facing product identical in both environments.

## Scaling

The web service should be stateless once cloud persistence is introduced.

Long-running operations belong in workers:

- repository ingestion
- document parsing
- embedding
- index rebuilds
- benchmark runs
- scheduled synchronization

## Security

Authentication and authorization must be enforced before retrieval. The LLM must never receive content that the requesting user is not authorized to access.
