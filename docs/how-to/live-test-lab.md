# Live Test Lab

The Live Test Lab executes a real public GitHub repository through the product pipeline and persists the run for later inspection.

## Browser

Open `/evaluation/live-lab`, enter a public `owner/name` repository, select `local`, `openai`, or `bedrock`, and run the benchmark.

Local mode exercises ingestion, indexing, retrieval, agent orchestration, citations and confidence without making an external LLM call. OpenAI and Bedrock modes make real provider calls only when credentials are configured.

## CLI

```bash
python -m knowledge_fabric.cli live-test --repo psf/requests --provider local
python -m knowledge_fabric.cli live-test --repo psf/requests --provider openai --model gpt-4.1-mini
python -m knowledge_fabric.cli live-test --repo psf/requests --provider bedrock
```

## What is persisted

Runs are stored in `data/live_benchmarks.json`. Each run includes repository/ref, provider/model, ingestion statistics, each benchmark question, answer, citations, confidence, latency, cache state, and summary metrics.

## No fake success

If credentials are missing, the run is marked `blocked`. If GitHub, indexing, retrieval, or generation fails, the run is marked `failed`. The system never converts a skipped provider call into a passing LLM result.

## Production extension

For CI, replace the browser's ad-hoc cases with a versioned golden dataset and add pass/fail gates for retrieval recall, citation coverage, groundedness, latency and cost.

## Benchmark Studio

Use `/evaluation/benchmark-studio` to compare multiple repository/provider/model configurations against the same question set. Results are persisted in `data/benchmark_studio.json` and ranked using a transparent quality score based on citation coverage, high-confidence evidence and successful cases. The score is an engineering comparison metric, not a claim of factual truth.
