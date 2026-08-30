# Live Test Lab and Benchmark Studio

## Live Test Lab

The Live Test Lab validates the complete pipeline against a real repository.

```text
GitHub
  ↓
Ingestion
  ↓
Chunking / symbols
  ↓
Index
  ↓
Retrieval
  ↓
Reranking
  ↓
Agent/tools
  ↓
LLM
  ↓
Citations / confidence
```

Providers:

- Local
- OpenAI-compatible
- Amazon Bedrock

A missing credential must result in `BLOCKED`, not a fake successful result.

## Recommended first benchmark

Repository:

```text
psf/requests
```

Run 5 questions first.

Then test:

- a larger framework
- your own repository
- an unknown-answer question
- a cross-file question
- a symbol/dependency question

## Benchmark Studio

Benchmark Studio compares multiple configurations using the same question set.

Example:

| Configuration | Provider | Reranker | Agent |
|---|---|---|---|
| Local baseline | Local | Off | Off |
| RAG | Bedrock | On | Off |
| Agentic RAG | Bedrock | On | On |

Track:

- success rate
- citation coverage
- groundedness
- answer quality
- average latency
- P95 latency
- token usage
- estimated cost

## Regression gate

Maintain a golden question set and compare every significant change against a baseline.

A release should fail if quality falls below agreed thresholds.
