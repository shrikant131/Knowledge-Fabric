"""Bounded agent orchestration with explicit, permission-aware tools.

Tool selection here is intentionally rule-based, not LLM-driven reasoning
-- there is no model in this sandbox capable of genuinely deciding which
tool to call next. This mirrors the same honest pattern as MockGenerator:
a real Bedrock/Anthropic/OpenAI-backed agent would use each provider's
native tool-calling API to choose dynamically; this heuristic policy is a
labeled stand-in, not a claim of real reasoning. See KnowledgeToolRegistry
for the tool contracts themselves, which are real and provider-agnostic
regardless of who -- rule or model -- decides to call them.
"""
from __future__ import annotations
from dataclasses import dataclass
import re, time
from knowledge_fabric.types import RankedChunk
from knowledge_fabric.security import Principal

_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|`([^`]+)`')
# heuristics for when a step is asking about a specific named thing rather
# than a general concept -- capitalized identifiers (classes), snake_case
# identifiers (functions/vars), or an explicit quoted string to grep for
_SYMBOL_HINT_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:[A-Z][a-z0-9]*)*|[a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")
_LOOKUP_INTENT_RE = re.compile(r"\b(where is|find|locate|defined|definition of|implementation of|class |function )\b", re.I)
_USAGE_INTENT_RE = re.compile(r"\b(who calls|usages? of|used by|references? to|callers of)\b", re.I)


@dataclass
class ToolResult:
    name: str
    data: object


class KnowledgeToolRegistry:
    def __init__(self, pipeline, principal=None):
        self.pipeline=pipeline
        self.principal=principal or Principal()

    def search(self, query, top_k=None):
        """Hybrid semantic+lexical search. Best for conceptual/fuzzy
        questions where no exact identifier is named."""
        return self.pipeline.retrieve(query, top_k=top_k or self.pipeline.cfg.top_k, principal=self.principal)

    def get_document(self, item_id):
        """Return every authorized chunk belonging to one specific file."""
        chunks=[c for c in self.pipeline.store.chunks
                if c.item_id==item_id and self.pipeline.security.authorize_chunk(c,self.principal)]
        return {"item_id":item_id,"chunks":chunks}

    def find_symbol(self, symbol, top_k=10):
        """Exact/substring match against chunk symbol names (function,
        class, or doc heading). Deterministic -- no ranking ambiguity,
        unlike vector/lexical search. This is the tool that should win for
        "what does class X do" / "where is function Y defined" style
        questions; see the real-repo finding that motivated it."""
        s=symbol.lower()
        hits=[c for c in self.pipeline.store.chunks
              if c.symbol and s in c.symbol.lower() and self.pipeline.security.authorize_chunk(c,self.principal)]
        # prefer exact full-name matches over substring matches
        hits.sort(key=lambda c: 0 if (c.symbol or "").split(":")[-1].lower()==s else 1)
        return hits[:top_k]

    def grep_content(self, pattern, top_k=15, use_regex=False):
        """Exact substring or regex search over chunk BODY text (not just
        symbol names) -- finds usages, string literals, error messages,
        TODOs, anything find_symbol can't see because it only looks at
        names. Deterministic, like ripgrep over the indexed corpus."""
        try:
            rx = re.compile(pattern, re.IGNORECASE) if use_regex else None
        except re.error:
            rx = None
        needle = pattern.lower()
        hits=[]
        for c in self.pipeline.store.chunks:
            if not self.pipeline.security.authorize_chunk(c,self.principal):
                continue
            matched = bool(rx.search(c.text)) if rx else (needle in c.text.lower())
            if matched:
                hits.append(c)
        return hits[:top_k]

    def get_related(self, item_id):
        """Other files that share meaningful terms with the target file --
        a cheap stand-in for a real dependency/import graph."""
        target=self.get_document(item_id)
        if not target["chunks"]: return []
        terms=set(re.findall(r"[A-Za-z0-9_]{4,}", item_id.lower()))
        out=[]
        for c in self.pipeline.store.chunks:
            if c.item_id==item_id or not self.pipeline.security.authorize_chunk(c,self.principal): continue
            if terms & set(re.findall(r"[A-Za-z0-9_]{4,}", c.text.lower())): out.append(c)
        return out[:10]

    def compare_documents(self, a,b):
        ac='\n'.join(c.text for c in self.get_document(a)["chunks"])
        bc='\n'.join(c.text for c in self.get_document(b)["chunks"])
        return {"a":ac,"b":bc}

    def get_citation_url(self, chunk):
        """External link for a chunk (GitHub blob URL, Confluence page,
        etc.) if the connector captured one -- lets an answer point back
        to the real source, not just an internal chunk id."""
        return (chunk.extra or {}).get("url")

    def list_sources(self):
        """Stats on what's actually indexed -- lets the agent answer
        'what do you have access to' honestly instead of guessing."""
        by_item = {}
        for c in self.pipeline.store.chunks:
            if not self.pipeline.security.authorize_chunk(c, self.principal):
                continue
            by_item.setdefault(c.item_id, 0)
            by_item[c.item_id] += 1
        return {"source_id": self.pipeline.cfg.source_id, "file_count": len(by_item),
                "chunk_count": sum(by_item.values())}


def _extract_identifier_candidates(step: str) -> list[str]:
    """Pull out things that look like real identifiers (Class names,
    snake_case names) worth trying find_symbol on, ignoring common
    sentence-case words that just happen to start a sentence."""
    candidates = []
    for m in _SYMBOL_HINT_RE.finditer(step):
        tok = m.group(1)
        if len(tok) < 3:
            continue
        # snake_case or genuine CamelCase is a strong identifier signal;
        # a single capitalized word could just be the start of a sentence
        if "_" in tok or (tok != tok.capitalize() or (m.start() > 0 and step[m.start()-1] != ".")):
            candidates.append(tok)
    return candidates


def _extract_quoted(step: str) -> list[str]:
    out = []
    for m in _QUOTED_RE.finditer(step):
        out.append(next(g for g in m.groups() if g))
    return out


class KnowledgeFabricAgent:
    def __init__(self,pipeline,principal=None):
        self.pipeline=pipeline
        self.principal=principal or Principal()
        self.tools=KnowledgeToolRegistry(pipeline,self.principal)

    def plan(self, question):
        q=question.strip()
        parts=re.split(r"\s+(?:and|also|then)\s+|\?\s+", q, flags=re.I)
        parts=[p.strip(" ?.") for p in parts if len(p.strip())>5]
        # Explicit step budget prevents prompt/query explosion.
        return parts[:self.pipeline.cfg.max_agent_steps] or [q]

    def _choose_tools_for_step(self, step: str) -> list[tuple[str, list]]:
        """Rule-based tool selection (see module docstring for why this is
        rules, not model reasoning). Order matters: exact/deterministic
        tools are tried first since they're cheap and unambiguous when
        they hit; hybrid search always runs too as the recall fallback."""
        calls: list[tuple[str, list]] = []

        quoted = _extract_quoted(step)
        for q in quoted:
            calls.append(("grep_content", self.tools.grep_content(q)))

        if _LOOKUP_INTENT_RE.search(step) or _USAGE_INTENT_RE.search(step):
            for ident in _extract_identifier_candidates(step):
                symbol_hits = self.tools.find_symbol(ident)
                if symbol_hits:
                    calls.append(("find_symbol", symbol_hits))
                if _USAGE_INTENT_RE.search(step):
                    # a usage/caller question needs the identifier's
                    # appearances in OTHER code, not just its own definition
                    calls.append(("grep_content", self.tools.grep_content(ident)))

        calls.append(("search", self.tools.search(step)))
        return calls

    def run(self, question):
        started=time.perf_counter()
        plan=self.plan(question) if self.pipeline.cfg.enable_query_expansion else [question]
        evidence=[]; traces=[]
        for step_no, step in enumerate(plan,1):
            if time.perf_counter()-started > getattr(self.pipeline.cfg,"agent_time_budget_seconds",20):
                traces.append({"tool":"budget","status":"timeout","step":step_no})
                break
            for tool_name, raw_hits in self._choose_tools_for_step(step):
                if tool_name == "search":
                    ranked = raw_hits  # already list[RankedChunk]
                else:
                    # deterministic tools return list[Chunk]; wrap with a
                    # priority score so exact matches outrank fuzzy search
                    # hits for the same chunk during the final merge
                    ranked = [RankedChunk(c, 1_000.0) for c in raw_hits]
                evidence.extend(ranked)
                traces.append({"tool":tool_name,"query":step,"hits":len(ranked),"step":step_no})
        seen=set(); merged=[]
        for rc in sorted(evidence,key=lambda x:-x.score):
            if rc.chunk.chunk_id not in seen:
                seen.add(rc.chunk.chunk_id); merged.append(rc)
        return merged[:self.pipeline.cfg.top_k*2], traces, plan
