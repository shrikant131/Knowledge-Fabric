# Security Policy

## Reporting

Do not publish credentials, tokens, or sensitive vulnerability details in public issues.

Report security concerns privately to the repository maintainer.

## Secrets

Use environment variables locally and AWS Secrets Manager or an equivalent secret store in production.

For AWS, prefer workload IAM roles over long-lived access keys.

## Authorization

Production deployments must enforce authorization before retrieval so unauthorized documents never enter LLM context.
