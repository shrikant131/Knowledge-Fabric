"""Transparent, claim-oriented confidence diagnostics.

This module does not pretend lexical overlap is semantic truth. It separates
retrieval quality from answer-to-evidence support and exposes claim coverage so
the UI/evaluator can distinguish evidence from correctness.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass
class ConfidenceReport:
    retrieval: float
    evidence_coverage: float
    source_agreement: float
    groundedness_proxy: float
    claim_coverage: float
    overall: float
    label: str
    claims: list[dict]

def _tokens(s):
    return set(re.findall(r"[a-z0-9_]{4,}", s.lower()))

def _claims(answer):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", answer or "") if len(x.strip()) >= 12]

def calculate_confidence(question, retrieved, answer):
    if not retrieved:
        return ConfidenceReport(0,0,0,0,0,0,"low",[])
    scores=[max(0,min(1,r.get("normalized_score",r.get("score",0)))) for r in retrieved[:3]]
    retrieval=sum(scores)/len(scores)
    context_tokens=_tokens(" ".join(r.get("preview","") for r in retrieved))
    answer_for_scoring=answer
    if answer_for_scoring.startswith("[MockGenerator"):
        answer_for_scoring=answer_for_scoring.split("]\n\n",1)[-1]
    answer_tokens=_tokens(answer_for_scoring)
    question_tokens=_tokens(question)
    grounded=len(answer_tokens & context_tokens)/max(1,len(answer_tokens))
    evidence_coverage=len(question_tokens & context_tokens)/max(1,len(question_tokens))
    source_ids={r.get("item_id") for r in retrieved if r.get("item_id")}
    source_agreement=1.0 if len(source_ids)>=1 else 0.0

    claims=[]
    supported=0
    for claim in _claims(answer_for_scoring)[:20]:
        ct=_tokens(claim)
        best=None; best_score=0.0
        for r in retrieved:
            rt=_tokens(r.get("preview",""))
            score=len(ct & rt)/max(1,len(ct))
            if score>best_score: best_score=score; best=r
        ok=best_score >= .35 and best is not None
        supported += int(ok)
        claims.append({"claim":claim,"supported":ok,"support_score":round(best_score,3),
                       "citation":best.get("citation") if ok and best else None})
    claim_coverage=supported/len(claims) if claims else grounded
    # Retrieval and claim support are intentionally distinct. This is a
    # diagnostic, not a proof of factual correctness.
    overall=.45*retrieval+.40*claim_coverage+.15*evidence_coverage
    label="high" if overall>=.75 else "medium" if overall>=.50 else "low"
    return ConfidenceReport(round(retrieval,3),round(evidence_coverage,3),round(source_agreement,3),
                            round(grounded,3),round(claim_coverage,3),round(overall,3),label,claims)
