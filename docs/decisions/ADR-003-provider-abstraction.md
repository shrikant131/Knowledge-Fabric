# ADR-003: Provider abstraction

## Decision

LLM and embedding providers are configuration-selected adapters.

## Rationale

Provider availability changes by environment, cost, policy and deployment. The knowledge and agent layers should not depend on one vendor.
