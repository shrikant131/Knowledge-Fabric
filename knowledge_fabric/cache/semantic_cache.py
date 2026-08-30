"""Version-aware semantic cache with safe JSON/NPZ persistence."""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

@dataclass
class CacheEntry:
    query: str
    answer: str
    retrieved: list[dict]
    chunk_hashes: dict[str, str]
    namespace: str = "default"
    created_at: float = field(default_factory=time.time)
    config_fingerprint: str = ""

class SemanticCache:
    def __init__(self, dimension, cache_path, similarity_threshold=.97, ttl_seconds=7*24*3600, namespace="default"):
        self.dimension=dimension; self.cache_path=Path(cache_path)
        self.meta_path=self.cache_path.with_suffix(".json")
        self.vector_path=self.cache_path.with_suffix(".npz")
        self.similarity_threshold=similarity_threshold; self.ttl_seconds=ttl_seconds; self.namespace=namespace
        self._vectors=np.zeros((0,dimension),dtype="float32"); self._entries=[]
        if self.meta_path.exists() and self.vector_path.exists(): self._load()

    def lookup(self, query_vector, current_hashes, namespace=None, config_fingerprint=""):
        if not self._entries: return None
        q=np.asarray(query_vector,dtype="float32").reshape(-1)
        if q.shape[0] != self.dimension: return None
        v=self._vectors/(np.linalg.norm(self._vectors,axis=1,keepdims=True)+1e-8)
        q=q/(np.linalg.norm(q)+1e-8)
        sims=v@q; order=np.argsort(-sims)
        for idx in order:
            if sims[idx] < self.similarity_threshold: break
            e=self._entries[int(idx)]
            if namespace is not None and e.namespace != namespace: continue
            if config_fingerprint and e.config_fingerprint != config_fingerprint: continue
            if time.time()-e.created_at > self.ttl_seconds: continue
            if self._still_valid(e,current_hashes): return e
        return None

    def write(self, query_vector, entry):
        q=np.asarray(query_vector,dtype="float32").reshape(1,-1)
        if q.shape[1] != self.dimension: raise ValueError("cache vector dimension mismatch")
        self._vectors=np.concatenate([self._vectors,q],axis=0)
        self._entries.append(entry); self._save()

    def _still_valid(self, entry, current_hashes):
        return all(current_hashes.get(k)==v for k,v in entry.chunk_hashes.items())

    def _save(self):
        self.cache_path.parent.mkdir(parents=True,exist_ok=True)
        payload={"version":2,"entries":[e.__dict__ for e in self._entries]}
        tmp=self.meta_path.with_suffix(".tmp"); tmp.write_text(json.dumps(payload,ensure_ascii=False))
        np.savez_compressed(self.vector_path.with_suffix(".tmp.npz"),vectors=self._vectors)
        tmp.replace(self.meta_path)
        self.vector_path.with_suffix(".tmp.npz").replace(self.vector_path)

    def _load(self):
        data=json.loads(self.meta_path.read_text())
        self._entries=[CacheEntry(**e) for e in data.get("entries",[])]
        with np.load(self.vector_path,allow_pickle=False) as z: self._vectors=np.asarray(z["vectors"],dtype="float32")
        if len(self._entries)!=len(self._vectors): raise ValueError("cache metadata/vector count mismatch")
