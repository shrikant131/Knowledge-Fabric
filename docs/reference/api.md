# API reference

The Flask control plane exposes a small JSON API.

## Health

```http
GET /api/health
```

Returns product status and source/watch counts.

## List sources

```http
GET /api/sources
```

## Query a source

```http
POST /api/sources/{source_id}/query
Content-Type: application/json

{"question":"How does retry work?"}
```

The response includes the answer, retrieved evidence, citations, confidence and trace.

## Toggle LLM

```http
POST /api/sources/{source_id}/llm
Content-Type: application/json

{"enabled":true,"provider":"bedrock"}
```

## Web UI endpoints

- `GET /` — dashboard
- `GET /sources/new` — source registration form
- `POST /sources` — register source
- `POST /sources/{source_id}/ingest` — manual sync
- `POST /sources/{source_id}/watch/start` — start watcher
- `POST /sources/{source_id}/watch/stop` — stop watcher
- `GET|POST /sources/{source_id}/query` — query UI
- `GET /sources/{source_id}/settings` — settings UI
