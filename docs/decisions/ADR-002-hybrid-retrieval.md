# ADR-002: Hybrid retrieval

## Decision

Combine lexical, vector and symbol retrieval rather than depending on a single search signal.

## Rationale

Enterprise knowledge includes prose, exact terminology, identifiers and source code. Different retrieval signals fail differently, so fusion improves robustness.
