# Configuration reference

Configuration is represented by `PipelineConfig` and YAML manifests.

| Setting | Default | Purpose |
|---|---:|---|
| `source_id` | `local_files` | Stable source identifier |
| `connector_type` | `file` | Connector implementation |
| `connector_options` | `{}` | Connector-specific options |
| `trigger_type` | `scheduler` | Sync trigger |
| `poll_interval_seconds` | `60` | Poll interval |
| `embedder` | `local` | Embedding backend |
| `generator` | `mock` | Generation backend |
| `llm_enabled` | `false` | LLM switch |
| `llm_provider` | `bedrock` | Real provider selection |
| `bedrock_region` | `us-east-1` | AWS region |
| `bedrock_embed_model` | Titan embed v2 | Bedrock embedding model |
| `bedrock_chat_model` | Claude 3.5 Sonnet | Bedrock chat model |
| `openai_chat_model` | `gpt-4.1-mini` | OpenAI-compatible chat model |
| `index_dir` | `./data` | Local index/state directory |
| `top_k` | `5` | Retrieval result count |
| `max_tokens` | `800` | Generation budget |
| `enable_cache` | `true` | Semantic cache |
| `cache_similarity_threshold` | `0.97` | Cache match threshold |
| `enable_self_rag` | `true` | Corrective retrieval |
| `max_correction_rounds` | `2` | Correction budget |
| `enable_reranker` | `true` | Second-stage ranking |
| `reranker_weight` | `0.35` | Reranker influence |
| `enable_query_expansion` | `true` | Query decomposition/expansion |
| `max_context_chars` | `18000` | Context safety bound |
| `confidence_threshold` | `0.55` | Evidence confidence gate |
| `max_agent_steps` | `3` | Agent planning limit |
| `allowed_sensitivity` | public/internal | Retrieval policy |
