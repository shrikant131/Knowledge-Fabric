"""Lexical retrieval with rank_bm25 when available and a dependency-free fallback."""
from __future__ import annotations
import math, re
from collections import Counter
from knowledge_fabric.types import Chunk, RankedChunk
try:
    from rank_bm25 import BM25Okapi  # type: ignore
except Exception:  # pragma: no cover
    BM25Okapi = None

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STOPWORDS = {"a","an","the","is","are","was","were","be","been","being","of","in","on","at","to","for","and","or","but","if","so","with","as","by","from","this","that","these","those","it","its","who","what","when","where","why","how","which","does","do","did","has","have","had","can","could","should","would","will","shall","not","no","yes","i","you","he","she","we","they","them","his","her","their","our","your","my"}

def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text)
    expanded=[]
    for tok in tokens:
        low=tok.lower()
        if low not in _STOPWORDS: expanded.append(low)
        parts=re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", tok)
        if len(parts)>1: expanded.extend(p.lower() for p in parts if p.lower() not in _STOPWORDS)
    return expanded

class Bm25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks=chunks
        self._corpus_tokens=[_tokenize(c.text) for c in chunks]
        self._bm25=BM25Okapi(self._corpus_tokens) if BM25Okapi and self._corpus_tokens else None
        self._df=Counter(t for toks in self._corpus_tokens for t in set(toks))
        self._avgdl=(sum(map(len,self._corpus_tokens))/len(self._corpus_tokens)) if self._corpus_tokens else 1

    def search(self, query: str, top_k: int=10, allowed_chunk_ids: set[str] | None=None) -> list[RankedChunk]:
        if not self.chunks: return []
        q=_tokenize(query)
        if self._bm25:
            scores=self._bm25.get_scores(q)
        else:
            n=len(self.chunks); k1=1.5; b=.75
            scores=[]
            for toks in self._corpus_tokens:
                tf=Counter(toks); dl=len(toks); score=0.0
                for term in q:
                    f=tf.get(term,0)
                    if not f: continue
                    df=self._df.get(term,0)
                    idf=math.log(1+(n-df+0.5)/(df+0.5))
                    score += idf * (f*(k1+1))/(f+k1*(1-b+b*dl/self._avgdl))
                scores.append(score)
        ranked=sorted(range(len(scores)), key=lambda i:-scores[i])
        out=[]
        for i in ranked:
            if scores[i] <= 0: continue
            if allowed_chunk_ids is not None and self.chunks[i].chunk_id not in allowed_chunk_ids: continue
            out.append(RankedChunk(self.chunks[i], float(scores[i])))
            if len(out)>=top_k: break
        return out
