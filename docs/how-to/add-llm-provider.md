# Add an LLM provider

Generation providers should implement the same high-level contract: receive a bounded prompt/context and return an answer without changing retrieval semantics.

## Design rules

- Never make provider selection part of retrieval code.
- Keep credentials in environment variables or a secret manager.
- Provide a health check.
- Return actionable errors.
- Preserve citations and evidence metadata outside the provider response.
- Keep local/mock generation available.

Register the provider in the generation layer, add configuration fields, add an API/UI option, and add tests for enabled, disabled, unavailable and successful states.
