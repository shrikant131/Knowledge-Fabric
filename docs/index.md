# Knowledge Fabric Documentation

Knowledge Fabric is a local-first enterprise knowledge and agent platform combining multi-source ingestion, hybrid retrieval, explicit agent tools, optional LLM generation, citations, confidence and evaluation.

## Choose your path

| I want to... | Start here |
|---|---|
| Get the product running | [5-minute quickstart](tutorials/quickstart.md) |
| Learn the product end-to-end | [First knowledge workflow](tutorials/first-knowledge-workflow.md) |
| Enable an LLM | [Enable LLM generation](how-to/enable-llm.md) |
| Add a knowledge source | [Add a source](how-to/add-source.md) |
| Improve retrieval | [Tune RAG](how-to/tune-rag.md) |
| Troubleshoot a problem | [Troubleshooting](operations/troubleshooting.md) |
| Understand the architecture | [Architecture](architecture/overview.md) |
| Integrate via API | [API reference](reference/api.md) |
| Extend the agent | [Add an agent tool](how-to/add-agent-tool.md) |
| Deploy with Docker | [Docker deployment](operations/docker.md) |

## Documentation model

The documentation is intentionally split into tutorials, how-to guides, reference material and explanations. This keeps learning paths focused while keeping operational facts easy to consult.

## Product status

This repository is a **production-shaped POC**. Local mode is designed to work without external credentials. Enterprise deployment still requires hardening of identity, ACL enforcement, secrets management, persistence, observability and managed infrastructure.

- [Live GitHub + LLM smoke test](how-to/live-github-llm-test.md)
