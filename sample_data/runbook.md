# Incident Response Runbook

## Retry and Backoff Policy

All connector fetch operations use exponential backoff with a configurable
maximum number of attempts (default 5) and a base delay of 2 seconds. This
prevents overwhelming a source system during transient outages while still
recovering quickly once the source is healthy again.

If retries are exhausted, the event is written to a per-source dead-letter
queue with full context (payload, error, attempt count) rather than being
dropped silently. On-call engineers should check the dead-letter queue
during any connector-related incident.

## Escalation Policy

If a connector has been failing for more than 30 minutes, page the on-call
data platform engineer. Include the source_id, the error rate, and whether
the dead-letter queue is growing.

## Idempotency Notes

Because ingestion is at-least-once, every chunk write is keyed by
(source_id, item_id, chunk_index, content_hash). Re-processing the same
event is a safe no-op overwrite, not a duplicate -- this should not be
treated as an incident by itself.


## New Section Added Live
This paragraph was added while the watcher was running, to prove the scheduler picks up file changes automatically without a manual ingest call.
