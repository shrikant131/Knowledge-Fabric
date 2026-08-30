# Admin Control Plane

The Admin Console is the central runtime control surface at `/admin`.

## Configuration lifecycle

Global defaults are stored in `data/admin_config.json`. Every change creates an append-only JSONL audit event in `data/admin_audit.jsonl` with timestamp, actor, reason, version, and old/new values.

Source-specific settings continue to live in `connectors_registry/*.yaml` so a source can be exported and version-controlled independently.

## Optimistic concurrency

`POST /api/admin/control-plane` accepts `expected_version`. If another administrator has changed the configuration since the page was loaded, the API returns HTTP 409 rather than silently overwriting the newer configuration.

## APIs

- `GET /api/admin/control-plane` — current global configuration and version
- `POST /api/admin/control-plane` — validate and persist global defaults
- `GET /api/admin/audit?limit=100` — recent configuration history
- `POST /api/admin/apply-defaults/<source_id>` — apply global defaults to one source
- `GET /api/admin/env-status` — credential presence only; secrets are never returned
- `POST /api/admin/test-provider` — provider readiness check
- `POST /api/admin/live-test` — readiness gate for the real GitHub + LLM benchmark

## Safety rules

The API rejects unknown control fields, validates numeric controls, and never writes secret values. Provider tests report readiness but do not claim a live generation call unless the provider can actually be initialized.
