# Docker deployment

Build and run:

```bash
docker compose up --build
```

The web UI is exposed on port `5050`.

For real providers, pass credentials through your deployment secret mechanism. Do not bake credentials into images.

For production, replace local filesystem state with managed persistent storage and use a proper process supervisor/orchestrator.
