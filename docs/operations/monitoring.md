# Monitoring and operational signals

At minimum monitor:

- source sync success/failure
- ingestion latency
- indexed document/chunk counts
- query latency
- cache hit rate
- retrieval empty-rate
- low-confidence answer rate
- LLM provider error rate
- evaluation regression status
- webhook failures

The POC exposes source health and query traces. A production deployment should export these signals to a centralized telemetry platform.
