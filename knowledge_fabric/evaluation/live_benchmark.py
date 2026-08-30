"""Persistent live GitHub -> RAG -> LLM benchmark runner."""
from __future__ import annotations
import json, os, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict, dataclass

DEFAULT_CASES = [
    {"id":"architecture","question":"What is this repository primarily for?"},
    {"id":"definition","question":"Where is the main request/session/client abstraction defined?"},
    {"id":"behavior","question":"How does the repository handle errors or retries?"},
    {"id":"docs","question":"What are the main usage or installation instructions?"},
    {"id":"unknown","question":"What feature is documented that does not exist in this repository?"},
]

@dataclass
class CaseResult:
    id: str
    question: str
    answer: str
    citations: list[str]
    confidence: dict
    latency_ms: int
    cache_hit: bool
    retrieved: int
    usage: dict = None
    error: str | None = None

class LiveBenchmarkStore:
    def __init__(self, path="./data/live_benchmarks.json"):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
    def list(self, limit=50):
        if not self.path.exists(): return []
        try: data=json.loads(self.path.read_text())
        except Exception: return []
        return data[-limit:][::-1]
    def append(self, run):
        data=[]
        if self.path.exists():
            try: data=json.loads(self.path.read_text())
            except Exception: data=[]
        data.append(run); self.path.write_text(json.dumps(data[-200:], indent=2))
        return run

def _provider_ready(provider, api_key_env="OPENAI_API_KEY"):
    if provider == "openai":
        return bool(os.getenv(api_key_env)), f"{api_key_env} is not configured"
    if provider == "bedrock":
        try:
            import boto3
            creds=boto3.Session(region_name=os.getenv("AWS_REGION") or "us-east-1").get_credentials()
            if not creds or not getattr(creds,"access_key",None):
                return False, "No AWS credentials resolved by the boto3 credential chain (including EC2/ECS role)"
            return True, ""
        except Exception as exc:
            return False, f"AWS credential resolution failed: {exc}"
    return True, ""

def run_benchmark(cfg, repo, provider="local", model=None, cases=None, ref=None, index_root="./data/live_runs"):
    from knowledge_fabric.pipeline import KnowledgeFabricPipeline
    from knowledge_fabric.config import PipelineConfig
    from knowledge_fabric.connectors.github_connector import GitHubConnector
    owner, name = _repo_parts(repo)
    run_id=f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    run_dir=Path(index_root)/run_id; run_dir.mkdir(parents=True, exist_ok=True)
    effective_provider = provider if provider in ("openai","bedrock") else "mock"
    opts={"owner":owner,"repo":name,"ref":ref or None,"token_env_var":"GITHUB_TOKEN"}
    run_cfg=PipelineConfig(**{**cfg.to_yaml_dict(), "source_id":run_id, "display_name":f"Live: {owner}/{name}", "connector_type":"github", "connector_options":opts, "index_dir":str(run_dir), "llm_enabled":effective_provider!="mock", "llm_provider":effective_provider, "generator":effective_provider, "bedrock_chat_model":model or cfg.bedrock_chat_model, "openai_chat_model":model or cfg.openai_chat_model})
    ready, reason=_provider_ready(effective_provider, run_cfg.openai_api_key_env)
    started=time.perf_counter()
    record={"run_id":run_id,"repo":f"{owner}/{name}","ref":opts["ref"],"provider":provider,"model":model,"started_at":datetime.now(timezone.utc).isoformat(),"status":"running"}
    if not ready:
        record.update(status="blocked", reason=reason, duration_ms=int((time.perf_counter()-started)*1000))
        return record
    try:
        pipeline=KnowledgeFabricPipeline(run_cfg)
        ingest=pipeline.ingest()
        selected=cases or DEFAULT_CASES
        results=[]
        for case in selected:
            t=time.perf_counter()
            try:
                result=pipeline.query(case["question"])
                results.append(asdict(CaseResult(case["id"],case["question"],result["answer"], [r["citation"] for r in result.get("retrieved",[])], result.get("confidence",{}), int((time.perf_counter()-t)*1000), bool(result.get("cache_hit")), len(result.get("retrieved",[])), result.get("usage",{}))))
            except Exception as e:
                results.append(asdict(CaseResult(case["id"],case["question"],"",[],{},int((time.perf_counter()-t)*1000),False,0,{},str(e))))
        good=[r for r in results if not r["error"]]
        grounded=sum(1 for r in good if r["citations"] and r["confidence"].get("claim_coverage",0)>=run_cfg.confidence_threshold)/len(good) if good else 0
        lats=sorted(r["latency_ms"] for r in good)
        total_in=sum((r.get("usage") or {}).get("input_tokens",0) or 0 for r in good)
        total_out=sum((r.get("usage") or {}).get("output_tokens",0) or 0 for r in good)
        p95=lats[min(len(lats)-1,max(0,int(round(.95*(len(lats)-1)))))] if lats else None
        record.update(status="completed", duration_ms=int((time.perf_counter()-started)*1000), ingest=ingest, cases=results,
                      metrics={"cases":len(results),"successful_cases":len(good),
                               "citation_coverage":round(sum(bool(r["citations"]) for r in good)/len(good),3) if good else 0,
                               "groundedness_proxy":round(sum(r["confidence"].get("claim_coverage",0) for r in good)/len(good),3) if good else 0,
                               "high_confidence_with_evidence":round(grounded,3),
                               "avg_latency_ms":round(sum(r["latency_ms"] for r in good)/len(good),1) if good else None,
                               "p95_latency_ms":p95,"input_tokens":total_in,"output_tokens":total_out})
    except Exception as e:
        record.update(status="failed", reason=str(e), duration_ms=int((time.perf_counter()-started)*1000))
    return record

def _repo_parts(repo):
    value=(repo or "").strip().removeprefix("https://github.com/").removeprefix("http://github.com/").strip("/")
    parts=value.split("/")
    if len(parts)<2: raise ValueError("GitHub repository must look like owner/name")
    return parts[0],parts[1]
