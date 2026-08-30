from __future__ import annotations
from dataclasses import dataclass, field
import os, yaml

@dataclass
class PipelineConfig:
    source_id: str = "local_files"
    tenant_id: str = "local"
    display_name: str = ""
    connector_type: str = "file"
    connector_options: dict = field(default_factory=dict)
    trigger_type: str = "scheduler"
    poll_interval_seconds: int = 60
    embedder: str = "local"
    generator: str = "mock"
    llm_enabled: bool = False
    llm_provider: str = "bedrock"  # local | bedrock | openai | mock
    local_llm_model: str = "llama3.2:3b"
    local_llm_base_url: str = "http://127.0.0.1:11434"
    local_llm_timeout: int = 120
    bedrock_region: str = "us-east-1"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"
    bedrock_chat_model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    openai_chat_model: str = "gpt-4.1-mini"
    openai_api_key_env: str = "OPENAI_API_KEY"
    openai_base_url: str = "https://api.openai.com/v1/chat/completions"
    github_token_env: str = "GITHUB_TOKEN"
    index_dir: str = "./data"
    top_k: int = 5
    max_tokens: int = 800
    enable_cache: bool = True
    cache_similarity_threshold: float = 0.97
    enable_self_rag: bool = True
    max_correction_rounds: int = 2
    min_lexical_hits: int = 1
    min_vector_similarity: float = 0.08
    symbol_match_weight: float = 3.0
    enable_reranker: bool = True
    reranker_weight: float = 0.35
    enable_query_expansion: bool = True
    max_context_chars: int = 18000
    confidence_threshold: float = 0.55
    max_agent_steps: int = 3
    agent_time_budget_seconds: int = 20
    max_tool_results: int = 100
    allowed_sensitivity: list[str] = field(default_factory=lambda: ["public", "internal"])
    public_access: bool = True
    allowed_users: list[str] = field(default_factory=list)
    allowed_groups: list[str] = field(default_factory=list)
    max_upload_bytes: int = 25 * 1024 * 1024
    max_query_chars: int = 8000
    max_requests_per_minute: int = 60
    cache_namespace: str = "default"

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        with open(path, encoding="utf-8") as f: raw = yaml.safe_load(f) or {}
        known = {k:v for k,v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_yaml_dict(self) -> dict:
        return {k:getattr(self,k) for k in self.__dataclass_fields__}

    def effective_llm_enabled(self) -> bool:
        if self.generator in {"local", "bedrock", "openai"}: return True
        return bool(self.llm_enabled)
