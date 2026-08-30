# Developer Guide

## Local development

Create the Python environment:

```bash
python local_install.py
```

Start:

```bash
kf start
```

Inspect:

```bash
kf status
```

Query:

```bash
kf query "How does authentication work?"
```

Evaluate:

```bash
kf evaluate
```

## Design rule

All major product capabilities should be accessible through:

1. Browser UI
2. API/service layer
3. CLI where operationally useful

Do not create separate business logic for the UI and CLI.

## Deployment rule

The local deployment must not depend on Docker.

Docker/container images are supported for cloud environments, but Python remains the canonical local developer installation.

## Testing

At minimum validate:

- syntax
- unit tests
- ingestion
- retrieval
- citations
- provider readiness
- live LLM path
- benchmark persistence
- authorization boundaries
- cloud startup

Never report a live provider test as successful when credentials or network access prevented execution.
