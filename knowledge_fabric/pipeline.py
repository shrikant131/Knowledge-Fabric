"""Production-shaped Knowledge Fabric orchestration."""
from __future__ import annotations
import numpy as np
import hashlib, json
from knowledge_fabric.security import Principal
from knowledge_fabric.cache.semantic_cache import CacheEntry, SemanticCache
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.connectors.factory import build_connector
from knowledge_fabric.evaluation.query_log import QueryLog, new_entry
from knowledge_fabric.evaluation.confidence import calculate_confidence
from knowledge_fabric.generation.prompts import build_prompt
from knowledge_fabric.retrieval.bm25_index import Bm25Index
from knowledge_fabric.retrieval.hybrid import reciprocal_rank_fusion
from knowledge_fabric.retrieval.router import route_query
from knowledge_fabric.retrieval.symbol_match import symbol_match_results
from knowledge_fabric.retrieval.reranker import rerank
from knowledge_fabric.security import SecurityPolicy
from knowledge_fabric.agent import KnowledgeFabricAgent
from knowledge_fabric.types import RankedChunk
from knowledge_fabric.vectorstore.faiss_store import FaissVectorStore

def _build_embedder(cfg):
    if cfg.embedder == "bedrock":
        from knowledge_fabric.embeddings.bedrock_embedder import BedrockEmbedder
        return BedrockEmbedder(model_id=cfg.bedrock_embed_model, region_name=cfg.bedrock_region)
    from knowledge_fabric.embeddings.local_embedder import LocalTfidfEmbedder
    return LocalTfidfEmbedder(state_path=f"{cfg.index_dir}/{cfg.source_id}.embedder.json")

def _build_generator(cfg):
    provider = cfg.llm_provider if cfg.effective_llm_enabled() else "mock"
    if provider == "local":
        from knowledge_fabric.generation.local_generator import LocalGenerator
        return LocalGenerator(model_id=cfg.local_llm_model, base_url=cfg.local_llm_base_url, timeout=cfg.local_llm_timeout)
    if provider == "bedrock":
        from knowledge_fabric.generation.bedrock_generator import BedrockGenerator
        return BedrockGenerator(model_id=cfg.bedrock_chat_model, region_name=cfg.bedrock_region, api_key_env=cfg.bedrock_api_key_env)
    if provider == "openai":
        from knowledge_fabric.generation.openai_generator import OpenAIGenerator
        return OpenAIGenerator(model_id=cfg.openai_chat_model, api_key_env=cfg.openai_api_key_env, base_url=cfg.openai_base_url)
    from knowledge_fabric.generation.mock_generator import MockGenerator
    return MockGenerator()

class KnowledgeFabricPipeline:
    def __init__(self,cfg):
        self.cfg=cfg; self.connector=build_connector(cfg); self.embedder=_build_embedder(cfg); self.generator=_build_generator(cfg)
        self.store=FaissVectorStore(dimension=self.embedder.dimension,index_path=f"{cfg.index_dir}/{cfg.source_id}.faiss")
        self.cache=SemanticCache(dimension=self.embedder.dimension,cache_path=f"{cfg.index_dir}/{cfg.source_id}.cache.pkl",similarity_threshold=cfg.cache_similarity_threshold)
        self.query_log=QueryLog(f"{cfg.index_dir}/{cfg.source_id}.querylog.jsonl"); self.security=SecurityPolicy(cfg.allowed_sensitivity,cfg.allowed_users,cfg.allowed_groups,cfg.public_access); self.agent=KnowledgeFabricAgent(self); self.config_fingerprint=self._config_fingerprint()

    def ingest(self)->dict:
        all_items=list(self.connector.fetch()); seen=self.store.all_content_hashes(); changed=self.connector.detect_delta(all_items,seen); current_ids={i.item_id for i in all_items}; deleted=set(seen)-current_ids
        if deleted:self.store.remove_items(deleted)
        if not changed:
            self.store.set_item_hashes({i.item_id:i.content_hash for i in all_items})
            self.store.save()
            return {"items_scanned":len(all_items),"items_changed":0,"items_deleted":len(deleted),"chunks_ingested":0,"total_chunks":len(self.store.chunks)}
        changed_ids={i.item_id for i in changed}; self.store.remove_items(changed_ids); changed_chunks=[]
        for item in changed:changed_chunks.extend(self.connector.chunk(self.connector.parse(item)))
        for c in changed_chunks:c.extra["tenant_id"]=self.cfg.tenant_id
        changed_chunks=self.security.filter_chunks(changed_chunks,Principal(user_id="ingest",tenant_id=self.cfg.tenant_id,authenticated=True))
        if hasattr(self.embedder,"fit"):
            all_chunks=[]
            for item in all_items:all_chunks.extend(self.connector.chunk(self.connector.parse(item)))
            for c in all_chunks:c.extra["tenant_id"]=self.cfg.tenant_id
            all_chunks=self.security.filter_chunks(all_chunks,Principal(user_id="ingest",tenant_id=self.cfg.tenant_id,authenticated=True)); self.embedder.fit([c.text for c in all_chunks] or ["empty knowledge base"]); vectors=self.embedder.embed([c.text for c in all_chunks]) if all_chunks else np.empty((0,self.embedder.dimension),dtype="float32"); self.store.replace_all(all_chunks,vectors)
        else:
            vectors=self.embedder.embed([c.text for c in changed_chunks]) if changed_chunks else np.empty((0,self.embedder.dimension),dtype="float32"); self.store.upsert(changed_chunks,vectors)
        self.store.set_item_hashes({i.item_id:i.content_hash for i in all_items}); self.store.save()
        return {"items_scanned":len(all_items),"items_changed":len(changed),"items_deleted":len(deleted),"chunks_ingested":len(changed_chunks),"total_chunks":len(self.store.chunks)}

    def retrieve(self,question:str,top_k:int|None=None,principal:Principal|None=None)->list[RankedChunk]:
        top_k=top_k or self.cfg.top_k; principal=principal or Principal(); qv=self.embedder.embed_one(question); lexical,vector=self._raw_retrieve(question,qv,2,principal); allowed=self.security.allowed_chunk_ids(self.store.chunks,principal); symbol=symbol_match_results(question,[c for c in self.store.chunks if c.chunk_id in allowed],top_k=top_k*2); fused=reciprocal_rank_fusion([lexical,vector,symbol],top_k=max(top_k*3,top_k),weights=[1,1,self.cfg.symbol_match_weight]); return rerank(question,fused,top_k=top_k,weight=self.cfg.reranker_weight) if self.cfg.enable_reranker else fused[:top_k]

    def query(self,question:str,principal:Principal|None=None)->dict:
        question=question.strip()
        if not question:raise ValueError("Question cannot be empty")
        if len(question)>self.cfg.max_query_chars:raise ValueError(f"Question exceeds {self.cfg.max_query_chars} characters")
        principal=principal or Principal(); intent=route_query(question); qv=self.embedder.embed_one(question); hashes=self.store.chunk_hashes_by_id()
        if self.cfg.enable_cache:
            cached=self.cache.lookup(qv,hashes,namespace=self.cfg.cache_namespace,config_fingerprint=self.config_fingerprint)
            if cached is not None:return {"query":question,"intent":intent.label,"retrieved":cached.retrieved,"answer":cached.answer,"cache_hit":True,"corrective_rounds":0,"confidence":{"overall":.9,"label":"high"},"trace":[{"stage":"cache","status":"hit"}]}
        fused,rounds,low=self._retrieve_with_correction(question,qv,principal); system_prompt,user_prompt=build_prompt(question,fused)
        if low:user_prompt += "\n\nDo not guess. State that the knowledge base does not contain enough evidence."
        answer=self.generator.generate(system_prompt,user_prompt,max_tokens=self.cfg.max_tokens); usage=getattr(self.generator,"last_usage",{"input_tokens":0,"output_tokens":0}); retrieved=[]; max_score=max((r.score for r in fused),default=1.0) or 1.0
        for rc in fused:retrieved.append({"citation":rc.chunk.citation_label(),"score":round(rc.score,4),"normalized_score":round(min(1,rc.score/max_score),4),"preview":rc.chunk.text[:300].replace("\n"," "),"chunk_id":rc.chunk.chunk_id,"item_id":rc.chunk.item_id,"symbol":rc.chunk.symbol,"sensitivity":rc.chunk.sensitivity})
        confidence=calculate_confidence(question,retrieved,answer)
        if low and not self.cfg.effective_llm_enabled():answer="I couldn't find enough evidence in the indexed knowledge to answer confidently.\n\n"+answer
        if self.cfg.enable_cache and fused and not low and confidence.overall>=self.cfg.confidence_threshold:self.cache.write(qv,CacheEntry(query=question,answer=answer,retrieved=retrieved,chunk_hashes={r.chunk.chunk_id:r.chunk.content_hash for r in fused},namespace=self.cfg.cache_namespace,config_fingerprint=self.config_fingerprint))
        trace=[{"stage":"route","intent":intent.label},{"stage":"retrieve","hits":len(fused),"corrective_rounds":rounds},{"stage":"generation","provider":self.cfg.llm_provider if self.cfg.effective_llm_enabled() else "deterministic"},{"stage":"confidence","score":confidence.overall,"label":confidence.label}]; self._log(question,intent.label,retrieved,answer,False,rounds)
        return {"query":question,"intent":intent.label,"retrieved":retrieved,"answer":answer,"cache_hit":False,"corrective_rounds":rounds,"low_confidence":low,"confidence":confidence.__dict__,"trace":trace,"usage":usage,"model":getattr(self.generator,"model_id",None)}

    def _retrieve_with_correction(self,question,qv,principal):
        current=question; rounds=0; plan=KnowledgeFabricAgent(self,principal).plan(question) if self.cfg.enable_query_expansion else [question]
        while rounds<=self.cfg.max_correction_rounds:
            queries=plan if rounds==0 else [current]; lexical_all=[]; vector_all=[]; symbol_all=[]
            for q in queries[:self.cfg.max_agent_steps]:
                qvec=self.embedder.embed_one(q); lexical,vector=self._raw_retrieve(q,qvec,2+rounds,principal); lexical_all.extend(lexical); vector_all.extend(vector); allowed=self.security.allowed_chunk_ids(self.store.chunks,principal); symbol_all.extend(symbol_match_results(q,[c for c in self.store.chunks if c.chunk_id in allowed],top_k=self.cfg.top_k*(2+rounds)))
            fused=reciprocal_rank_fusion([lexical_all,vector_all,symbol_all],top_k=self.cfg.top_k*3,weights=[1,1,self.cfg.symbol_match_weight]); fused=rerank(question,fused,top_k=self.cfg.top_k,weight=self.cfg.reranker_weight) if self.cfg.enable_reranker else fused[:self.cfg.top_k]
            if not self.cfg.enable_self_rag or self._is_sufficient(lexical_all,vector_all,symbol_all):return fused,rounds,False
            rounds+=1; current=f"{question} relevant implementation policy behavior failure dependencies"
        return fused,rounds,True

    def _raw_retrieve(self,question,qv,top_k_multiplier=2,principal=None):
        allowed=self.security.allowed_chunk_ids(self.store.chunks,principal or Principal()); bm25=Bm25Index(self.store.chunks); return bm25.search(question,self.cfg.top_k*top_k_multiplier,allowed),self.store.search(qv,self.cfg.top_k*top_k_multiplier,allowed)
    def _is_sufficient(self,lexical,vector,symbol=()):return len(lexical)>=self.cfg.min_lexical_hits or (vector and vector[0].score>=self.cfg.min_vector_similarity) or bool(symbol)
    def _config_fingerprint(self):
        relevant={"source_id":self.cfg.source_id,"embedder":self.cfg.embedder,"top_k":self.cfg.top_k,"reranker":self.cfg.enable_reranker,"provider":self.cfg.llm_provider if self.cfg.effective_llm_enabled() else "deterministic","model":self.cfg.local_llm_model if self.cfg.llm_provider=="local" else self.cfg.bedrock_chat_model if self.cfg.llm_provider=="bedrock" else self.cfg.openai_chat_model}; return hashlib.sha256(json.dumps(relevant,sort_keys=True).encode()).hexdigest()
    def _log(self,question,intent,retrieved,answer,cache_hit,corrective_rounds=0):entry=new_entry(self.cfg.source_id,question,intent,retrieved,answer); entry.cache_hit=cache_hit; entry.corrective_rounds=corrective_rounds; self.query_log.append(entry)
