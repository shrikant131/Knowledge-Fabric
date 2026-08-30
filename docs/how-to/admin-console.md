# Admin Console

The Knowledge Fabric Admin Console is the central control plane for the POC. Open `http://localhost:5050/admin` after starting the application.

## Sections

- **Overview** — source count, indexed chunks, watchers, LLM-enabled sources and source errors.
- **AI & Models** — provider readiness and per-source AI profiles.
- **Retrieval** — Top-K, reranking, query expansion, self-RAG, cache and confidence settings.
- **Agent** — available bounded tools and planning behavior.
- **Knowledge** — source health, chunks, run counts, sync and query shortcuts.
- **Connectors** — local files, GitHub, Confluence and SharePoint source setup.
- **Ingestion** — watcher status and failed-run visibility.
- **Security** — POC controls and explicit production security boundaries.
- **Evaluation / Live Test Lab** — public GitHub repository benchmark readiness and test entry point.
- **Observability** — trace, performance and quality signals.
- **System** — environment credential visibility and runtime details.

## LLM switch

LLM is configured per source. `OFF` means the pipeline uses the local generator and makes no model API calls. `ON` selects the configured provider. Use **Test OpenAI** or **Test Bedrock** before enabling a provider.

The UI intentionally reports a provider as unavailable when credentials are absent. It never presents a simulated successful live call as a real LLM result.

## Retrieval tuning

Change one setting at a time and run the golden evaluation after each change. Recommended baseline:

- Top K: 5
- Reranker: ON
- Query expansion: ON
- Self-RAG: ON
- Cache: ON
- Confidence threshold: 0.55

For experiments, record the configuration and compare precision, recall, groundedness and citation accuracy.

## Live GitHub testing

1. Add a `github` source with a public repository such as `psf/requests`.
2. Sync the source.
3. Open **Evaluation → Live Test Lab**.
4. Select OpenAI-compatible or Bedrock.
5. Check readiness.
6. Only when credentials and network access are available, run `tools_live_llm_test.py` to execute the actual benchmark.

The current hosted execution environment may not have external API credentials/network access. A blocked readiness response is expected in that case.
