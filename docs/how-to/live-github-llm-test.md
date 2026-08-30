# Live GitHub + LLM smoke test

This test exercises the product end-to-end using a public GitHub repository:

`GitHub → ingestion → code/document chunking → hybrid retrieval → reranking → LLM → citations/confidence/trace`

GitHub's public repository APIs can be used without authentication for public repositories; the connector uses the repository tree and blob APIs. See the official GitHub API documentation for the repository contents and archive endpoints.

## OpenAI-compatible provider

```bash
export OPENAI_API_KEY="..."
python tools_live_llm_test.py --repo psf/requests --provider openai
```

## Amazon Bedrock

Use the normal AWS credential chain and make sure the selected model is enabled for your account/region:

```bash
python tools_live_llm_test.py --repo psf/requests --provider bedrock
```

## What the test verifies

1. Public repository discovery.
2. Repository file ingestion.
3. Code-symbol extraction.
4. Hybrid retrieval.
5. Reranking.
6. Real LLM generation.
7. Source citations.
8. Confidence and trace output.
9. No fabricated live result when credentials/network are unavailable.

For a larger codebase, try `pallets/flask` after the smaller `psf/requests` smoke test.
