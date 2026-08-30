# AWS Cost Guardrails for the POC

Because Bedrock inference can incur charges, treat the free tier/credits as a budget rather than unlimited capacity.

## Safe starting pattern

Run:

```text
1 repository
5 questions
1 model
1 benchmark configuration
```

Then expand.

## Recommended controls

- AWS billing alerts
- Free Tier usage alerts where available
- small benchmark datasets initially
- avoid repeated full repository re-ingestion
- enable caching where appropriate
- prefer local retrieval for development
- set application-level request/token limits
- record model usage for every benchmark

## Before production

Add:

- daily budget
- monthly budget
- per-user limits
- per-query token limits
- provider fallback policy
- cost dashboard
- automatic benchmark throttling
