# Playground, Quick Start and CLI

Knowledge Fabric has three complementary entry points.

## Browser Playground

`/playground` is the primary product experience. It is intentionally low-friction: select a knowledge source, ask a question, and inspect the answer, citations, confidence, and pipeline flow.

## Quick Start

`/quick-start` is the onboarding wizard. It offers three paths:

- Sample knowledge — instant local demo.
- Browser file upload — uploads supported documents/code into the local quick-upload area and indexes them.
- Public GitHub repository — imports a public `owner/repository` without requiring a GitHub token.

LLM credentials are optional. Local mode is the default.

## Admin Console

`/admin` is the control plane for advanced configuration, source operations, AI/RAG settings, audit history, evaluation, and system status.

## CLI

```bash
python -m knowledge_fabric.cli init
python -m knowledge_fabric.cli start
python -m knowledge_fabric.cli status
python -m knowledge_fabric.cli query "How does the retry policy work?"
python -m knowledge_fabric.cli evaluate
```

The CLI and browser use the same pipeline abstractions; they are not separate implementations.

## Recommended demo

1. Run `./start.sh`.
2. Open `/playground`.
3. Click **Try Sample Knowledge**.
4. Ask a question.
5. Open **Admin** for detailed controls.
6. Open **Live Test Lab** when a real provider is configured.
