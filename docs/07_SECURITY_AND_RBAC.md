# Security and RBAC Roadmap

## Current POC principle

Local mode should be easy to start.

Cloud deployments should use an IAM role for AWS services and avoid static AWS credentials.

## Production identity

Recommended:

```text
OIDC / SSO
   ↓
User
   ↓
Groups / Roles
   ↓
Knowledge-base permissions
   ↓
Document ACL filtering
   ↓
Retriever
```

## Roles

Suggested initial roles:

- Platform Admin
- Knowledge Admin
- Evaluator
- Contributor
- Viewer

## Retrieval-time ACL

Authorization must be applied before context reaches the LLM.

Never use a post-generation filter as the primary security boundary.

## Audit

Record:

- actor
- timestamp
- action
- resource
- old/new configuration where applicable
- result

## Secrets

Use:

- local environment variables for local development
- AWS Secrets Manager or equivalent cloud secret storage in production

Never commit API keys or cloud credentials to Git.
