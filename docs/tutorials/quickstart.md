# Quickstart

Knowledge Fabric is designed to be usable before any LLM credentials are configured.

## Browser-first

Run:

```bash
./start.sh
```

Open `http://localhost:5050`. The application automatically bootstraps the included sample knowledge and takes you to the Playground.

Choose one of:

1. **Try Sample Knowledge** — zero configuration.
2. **Add Files** — point to a local folder.
3. **Connect GitHub** — enter a public `owner/repository`.

The system ingests, chunks, indexes, and exposes the knowledge for questions. Local mode does not call an LLM.

## CLI-first

```bash
python -m knowledge_fabric.cli init
python -m knowledge_fabric.cli ingest
python -m knowledge_fabric.cli query "How does the retry policy work?"
python -m knowledge_fabric.cli status
python -m knowledge_fabric.cli start
```

## Enable a real LLM later

Use **Admin → AI & Models**. Test the provider before enabling it. If credentials are absent, the product stays usable in local mode.

## Next steps

- [Live GitHub + LLM test](../how-to/live-github-llm-test.md)
- [Admin control plane](../ADMIN_CONTROL_PLANE.md)
- [Add a source](../how-to/add-source.md)
