# Security architecture

Security boundaries are designed around the principle that unauthorized information must not reach the model.

Current POC controls include sensitivity filtering before generation and environment-based secret references.

Production requirements:

- identity and SSO
- source/document ACL resolution
- tenant isolation
- secret manager integration
- encryption at rest/in transit
- audit trails
- prompt-injection defenses
- data retention policy
- administrator authorization
