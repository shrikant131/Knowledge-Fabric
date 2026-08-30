"""Production-shaped Knowledge Fabric orchestration.

The same API works in zero-LLM local mode and with a real provider. Retrieval,
agent tools, security filtering, caching, citations, confidence and traces are
kept provider-independent.
"""
from __future__ import annotations
import numpy as np
import hashlib, json
from knowledge_fabric.security import Principal
from knowledge_fabric.cache.semantic_cache import CacheEntry, SemanticCache
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.connectors.factory import build_connector
from knowledge_fabric.embeddings.base import Embedder
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
from knowledge_fabric.types import Chunk, RankedChunk
from knowledge_fabric.vectorstore.faiss_store import FaissVectorStore


def _build_embedder(cfg):
    if cfg.embedder == "bedrock":
        from knowledge_fabric.embeddings.bedrock_embedder import BedrockEmbedder
        return BedrockEmbedder(model_id=cfg.bedrock_embed_model, region_name=cfg.bedrock_region)
    from knowledge_fabric.embeddings.local_embedder import LocalTfidfEmbedder
    return LocalTfidfEmbedder(state_path=f"{cfg.index_dir}/{cfg.source_id}.embedder.json")


def _build_generator(cfg):
    provider = cfg.llm_provider if cfg.effective_llm_enabled() else "mock"
    if provider == "bedrock":
        from knowledge_fabric.generation.bedrock_generator import BedrockGenerator
        return BedrockGenerator(model_id=cfg.bedrock_chat_model, region_name=cfg.bedrock_region)
    if provider == "openai":
        from knowledge_fabric.generation.openai_generator import OpenAIGenerator
        return OpenAIGenerator(model_id=cfg.openai_chat_model, api_key_env=cfg.openai_api_key_env, base_url=cfg.openai_base_url)
    from knowledge_fabric.generation.mock_generator import MockGenerator
    return MockGenerator()


class KnowledgeFabricPipeline:
    def __init__(self, cfg):
        self.cfg=cfg
        self.connector=build_connector(cfg)
        self.embedder=_build_embedder(cfg)
        self.generator=_build_generator(cfg)
        self.store=FaissVectorStore(dimension=self.embedder.dimension,index_path=f"{cfg.index_dir}/{cfg.source_id}.faiss")
        self.cache=SemanticCache(dimension=self.embedder.dimension,cache_path=f"{cfg.index_dir}/{cfg.source_id}.cache.pkl",similarity_threshold=cfg.cache_similarity_threshold)
        self.query_log=QueryLog(f"{cfg.index_dir}/{cfg.source_id}.querylog.jsonl")
        self.security=SecurityPolicy(cfg.allowed_sensitivity, cfg.allowed_users, cfg.allowed_groups, cfg.public_access)
        self.agent=KnowledgeFabricAgent(self)
        self.config_fingerprint=self._config_fingerprint()

    def ingest(self)->dict:
        all_items=list(self.connector.fetch())
        seen=self.store.all_content_hashes()
        changed=self.connector.detect_delta(all_items,seen)
        current_ids={i.item_id for i in all_items}
        deleted=set(seen)-current_ids
        # Delete removed documents first.
        if deleted:
            self.store.remove_items(deleted)

        if not changed:
            return {"items_scanned":len(all_items),"items_changed":0,"items_deleted":len(deleted),
                    "chunks_ingested":0,"total_chunks":len(self.store.chunks)}

        changed_ids={i.item_id for i in changed}
        # Remove old chunks for changed documents.
        self.store.remove_items(changed_ids)

        changed_chunks=[]
        for item in changed:
            doc=self.connector.parse(item)
            changed_chunks.extend(self.connector.chunk(doc))
        for c in changed_chunks:
            c.extra["tenant_id"]=self.cfg.tenant_id
        changed_chunks=self.security.filter_chunks(changed_chunks, Principal(user_id="ingest", tenant_id=self.cfg.tenant_id, authenticated=True))

        # Local TF-IDF vocabulary is corpus-dependent, so it must be refit and
        # re-embedded as a whole. Semantic/remote embedders can update deltas.
        if hasattr(self.embedder,"fit"):
            all_chunks=[]
            for item in all_items:
                doc=self.connector.parse(item)
                all_chunks.extend(self.connector.chunk(doc))
            for c in all_chunks:
                c.extra["tenant_id"]=self.cfg.tenant_id
            all_chunks=self.security.filter_chunks(all_chunks, Principal(user_id="ingest", tenant_id=self.cfg.tenant_id, authenticated=True))
            self.embedder.fit([c.text for c in all_chunks] or ["empty knowledge base"])
            vectors=self.embedder.embed([c.text for c in all_chunks]) if all_chunks else np.empty((0,self.embedder.dimension),dtype="float32")
            self.store.replace_all(all_chunks,vectors)
            count=len(all_chunks)
        else:
            vectors=self.embedder.embed([c.text for c in changed_chunks]) if changed_chunks else np.empty((0,self.embedder.dimension),dtype="float32")
            self.store.upsert(changed_chunks,vectors)
            count=len(changed_chunks)
        self.store.save()
        return {"items_scanned":len(all_items),"items_changed":len(changed),"items_deleted":len(deleted),
                "chunks_ingested":count,"total_chunks":len(self.store.chunks)}

    def retrieve(self, question:str, top_k:int|None=None, principal: Principal|None=None)->list[RankedChunk]:
        top_k=top_k or self.cfg.top_k
        qv=self.embedder.embed_one(question)
        lexical,vector=self._raw_retrieve(question,qv,2,principal)
        allowed=self.security.allowed_chunk_ids(self.store.chunks, principal or Principal())
        symbol_candidates=[c for c in self.store.chunks if c.chunk_id in allowed]
        symbol=symbol_match_results(question,symbol_candidates,top_k=top_k*2)
        fused=reciprocal_rank_fusion([lexical,vector,symbol],top_k=max(top_k*3,top_k),weights=[1,1,self.cfg.symbol_match_weight])
        if self.cfg.enable_reranker: fused=rerank(question,fused,top_k=top_k,weight=self.cfg.reranker_weight)
        return fused

    def query(self,question:str, principal: Principal|None=None)->dict:
        question=question.strip()
        if not question: raise ValueError("Question cannot be empty")
        if len(question) > self.cfg.max_query_chars: raise ValueError(f"Question exceeds {self.cfg.max_query_chars} characters")
        principal=principal or Principal()
        intent=route_query(question)
        qv=self.embedder.embed_one(question)
        hashes=self.store.chunk_hashes_by_id()
        if self.cfg.enable_cache:
            cached=self.cache.lookup(qv,hashes,namespace=self.cfg.cache_namespace,config_fingerprint=self.config_fingerprint)
            if cached is not None:
                self._log(question,intent.label,cached.retrieved,cached.answer,True,0)
                return {"query":question,"intent":intent.label,"retrieved":cached.retrieved,"answer":cached.answer,"cache_hit":True,"corrective_rounds":0,"confidence":{"overall":.9,"label":"high","retrieval":.9,"evidence_coverage":.9,"source_agreement":1.0,"groundedness_proxy":.9,"claim_coverage":.9,"claims":[]},"trace":[{"stage":"cache","status":"hit"}]}

        fused,rounds,low=self._retrieve_with_correction(question,qv,principal)
        context=self._context(fused)
        system_prompt,user_prompt=build_prompt(question,fused)
        if low: user_prompt += "\n\nDo not guess. State that the knowledge base does not contain enough evidence."
        answer=self.generator.generate(system_prompt,user_prompt,max_tokens=self.cfg.max_tokens)
        usage=getattr(self.generator, "last_usage", {"input_tokens":0,"output_tokens":0})
        retrieved=[]
        max_score=max((r.score for r in fused),default=1.0) or 1.0
        for rc in fused:
            retrieved.append({"citation":rc.chunk.citation_label(),"score":round(rc.score,4),"normalized_score":round(min(1,rc.score/max_score),4),"preview":rc.chunk.text[:300].replace("\n"," "),"chunk_id":rc.chunk.chunk_id,"item_id":rc.chunk.item_id,"symbol":rc.chunk.symbol,"sensitivity":rc.chunk.sensitivity})
        confidence=calculate_confidence(question,retrieved,answer)
        if low or confidence.overall<self.cfg.confidence_threshold:
            answer = answer if self.cfg.effective_llm_enabled() else ("I couldn't find enough evidence in the indexed knowledge to answer confidently.\n\n" + (answer if answer else "No supported answer was found."))
        if self.cfg.enable_cache and fused and not low and confidence.overall>=self.cfg.confidence_threshold:
            self.cache.write(qv,CacheEntry(query=question,answer=answer,retrieved=retrieved,chunk_hashes={r.chunk.chunk_id:r.chunk.content_hash for r in fused},namespace=self.cfg.cache_namespace,config_fingerprint=self.config_fingerprint))
        trace=[{"stage":"route","intent":intent.label},{"stage":"retrieve","hits":len(fused),"corrective_rounds":rounds},{"stage":"rerank","enabled":self.cfg.enable_reranker},{"stage":"generation","provider":self.cfg.llm_provider if self.cfg.effective_llm_enabled() else "local"},{"stage":"confidence","score":confidence.overall,"label":confidence.label}]
        self._log(question,intent.label,retrieved,answer,False,rounds)
        return {"query":question,"intent":intent.label,"retrieved":retrieved,"answer":answer,"cache_hit":False,"corrective_rounds":rounds,"low_confidence":low,"confidence":confidence.__dict__,"trace":trace,"context_chars":len(context),"usage":usage,"model":getattr(self.generator,"model_id",None)}

    def _context(self,fused):
        out=[]; n=0
        for rc in fused:
            block=f"[{rc.chunk.citation_label()}]\n{rc.chunk.text.strip()}"
            if n+len(block)>self.cfg.max_context_chars: break
            out.append(block); n+=len(block)
        return "\n\n".join(out)

    def _retrieve_with_correction(self,question,qv,principal):
        current=question; rounds=0; fused=[]
        plan=KnowledgeFabricAgent(self, principal).plan(question) if self.cfg.enable_query_expansion else [question]
        while rounds<=self.cfg.max_correction_rounds:
            queries=plan if rounds==0 else [current]
            channels=[]
            lexical_all=[]; vector_all=[]; symbol_all=[]
            for q in queries[:self.cfg.max_agent_steps]:
                qvec=self.embedder.embed_one(q)
                lexical,vector=self._raw_retrieve(q,qvec,2+rounds,principal)
                allowed=self.security.allowed_chunk_ids(self.store.chunks, principal or Principal())
                symbol_candidates=[c for c in self.store.chunks if c.chunk_id in allowed]
                symbol=symbol_match_results(q,symbol_candidates,top_k=self.cfg.top_k*(2+rounds))
                lexical_all.extend(lexical); vector_all.extend(vector); symbol_all.extend(symbol)
            fused=reciprocal_rank_fusion([lexical_all,vector_all,symbol_all],top_k=self.cfg.top_k*3,weights=[1,1,self.cfg.symbol_match_weight])
            if self.cfg.enable_reranker: fused=rerank(question,fused,top_k=self.cfg.top_k,weight=self.cfg.reranker_weight)
            if not self.cfg.enable_self_rag or self._is_sufficient(lexical_all,vector_all,symbol_all): return fused,rounds,False
            rounds+=1; current=f"{question} relevant implementation policy behavior failure dependencies"
        return fused,rounds,True

    def _raw_retrieve(self,question,qv,top_k_multiplier=2,principal=None):
        allowed=self.security.allowed_chunk_ids(self.store.chunks, principal or Principal())
        bm25=Bm25Index(self.store.chunks)
        return bm25.search(question,self.cfg.top_k*top_k_multiplier,allowed), self.store.search(qv,self.cfg.top_k*top_k_multiplier,allowed)

    def _is_sufficient(self,lexical,vector,symbol=()):
        return len(lexical)>=self.cfg.min_lexical_hits or (vector and vector[0].score>=self.cfg.min_vector_similarity) or bool(symbol)

    def _config_fingerprint(self):
        relevant = {
            "source_id": self.cfg.source_id, "embedder": self.cfg.embedder,
            "top_k": self.cfg.top_k, "reranker": self.cfg.enable_reranker,
            "reranker_weight": self.cfg.reranker_weight,
            "symbol_match_weight": self.cfg.symbol_match_weight,
            "prompt_version": "v2",
            "provider": self.cfg.llm_provider if self.cfg.effective_llm_enabled() else "local",
            "model": self.cfg.bedrock_chat_model if self.cfg.llm_provider=="bedrock" else self.cfg.openai_chat_model,
        }
        return hashlib.sha256(json.dumps(relevant,sort_keys=True).encode()).hexdigest()

    def _log(self,question,intent,retrieved,answer,cache_hit,corrective_rounds=0):
        entry=new_entry(self.cfg.source_id,question,intent,retrieved,answer); entry.cache_hit=cache_hit; entry.corrective_rounds=corrective_rounds; self.query_log.append(entry)
