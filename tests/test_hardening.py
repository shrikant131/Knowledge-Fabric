from pathlib import Path
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.security import SecurityPolicy, Principal, ConstantTimeSecret, RateLimiter
from knowledge_fabric.types import Chunk
from knowledge_fabric.vectorstore.faiss_store import FaissVectorStore
import numpy as np

def test_secret_comparison_and_rate_limit():
    assert ConstantTimeSecret.matches("abc", "abc")
    assert not ConstantTimeSecret.matches("abc", "abd")
    limiter=RateLimiter(2,60)
    assert limiter.allow("x")
    assert limiter.allow("x")
    assert not limiter.allow("x")

def test_acl_and_tenant_filtering():
    chunks=[
        Chunk("1","s","a.py","public",None,"python","h",extra={"tenant_id":"t1","allowed_groups":["eng"]}),
        Chunk("2","s","b.py","internal",None,"python","h",extra={"tenant_id":"t2"}),
    ]
    policy=SecurityPolicy(["public","internal"],public_access=False)
    assert policy.filter_chunks(chunks,Principal("u",frozenset({"eng"}),"t1",True)) == [chunks[0]]
    assert policy.filter_chunks(chunks,Principal("u",frozenset(),"t1",True)) == []

def test_vector_store_uses_safe_serialization(tmp_path):
    path=tmp_path/"idx.faiss"
    store=FaissVectorStore(3,str(path))
    c=Chunk("1","s","a.py","hello",None,"python","hash",extra={"tenant_id":"local"})
    store.replace_all([c],np.array([[1,0,0]],dtype="float32")); store.save()
    assert path.with_suffix(".meta.json").exists()
    assert path.with_suffix(".vectors.npz").exists()
    assert not path.with_suffix(".meta.pkl").exists()
    reloaded=FaissVectorStore(3,str(path))
    assert reloaded.chunks[0].text=="hello"

def test_config_has_bounded_agent_and_query_controls():
    cfg=PipelineConfig()
    assert cfg.max_agent_steps >= 1
    assert cfg.agent_time_budget_seconds >= 1
    assert cfg.max_query_chars >= 100
