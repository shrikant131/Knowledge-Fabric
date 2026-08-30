# Example: local RAG without an LLM

Use the bundled manifest:

```bash
python -m knowledge_fabric.cli ingest --config manifest.yaml
python -m knowledge_fabric.cli query "How does retry work?" --config manifest.yaml
```

This path requires no external API credentials and is the canonical smoke test.
