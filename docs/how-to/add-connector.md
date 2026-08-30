# Build a connector

A connector is responsible for source access, not parsing policy or answer generation.

## Contract

A connector should provide stable source/item identifiers and enough metadata to construct `RawItem` records.

## Required behaviors

- initial discovery
- incremental change detection
- deletion detection when the source supports it
- retries for transient failures
- clear errors for permanent failures
- no secrets in returned content or logs

## Test matrix

| Scenario | Expected result |
|---|---|
| New item | indexed |
| Unchanged item | skipped |
| Changed item | reindexed |
| Deleted item | removed/tombstoned |
| Auth failure | clear error |
| Network timeout | retryable error |
