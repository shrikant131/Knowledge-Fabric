# Live GitHub + LLM Testing

The Live Test Lab is deliberately split into readiness and execution. Readiness must not be presented as a successful LLM test.

## Example

```bash
export OPENAI_API_KEY=...
python tools_live_llm_test.py --repo psf/requests --provider openai
```

For Bedrock, configure AWS credentials and run:

```bash
python tools_live_llm_test.py --repo psf/requests --provider bedrock
```

The benchmark should capture ingestion counts, retrieval metrics, answer grounding, citation correctness, latency, and failures. Unknown questions must be included to measure abstention/hallucination resistance.

## Recommended repositories

- `psf/requests` — Python package and clean symbol-level tests
- `pallets/flask` — framework-scale Python repository
- `kubernetes/kubernetes` — large repository/scalability stress test
