# AST + Knowledge Graph Implementation Plan

**Project:** Knowledge Fabric  
**Branch:** `main`  
**Baseline commit:** `336779745e121bb1f9ab227cfc9db36497c2d652`  
**Status:** Architecture and implementation roadmap

## 1. Purpose

Knowledge Fabric is evolving from a hybrid RAG platform into an enterprise knowledge and developer-intelligence platform that understands both **content** and **relationships**.

The target architecture combines:

- structure-aware code analysis
- Abstract Syntax Trees (ASTs)
- a persistent Knowledge Graph (KG)
- vector and lexical retrieval
- graph-aware retrieval
- citations and confidence
- agent tools and impact analysis
- Git and change-history metadata

The objective is to answer not only:

> What does this document or code say?

but also:

> How does this system work, what depends on it, what changed it, and what could be affected if I change it?

## 2. Current implementation baseline

The current Knowledge Fabric implementation already provides the foundation for this architecture:

- Structure-aware code chunking with AST/tree-sitter support where available and structured fallback parsing.
- Function/class-oriented code retrieval.
- Hybrid lexical, vector, and symbol retrieval.
- Reciprocal Rank Fusion (RRF).
- Reranking.
- Query expansion and corrective/self-RAG retrieval behavior.
- Semantic caching.
- Citations, confidence diagnostics, and decision traces.
- GitHub, local-file, Confluence, and SharePoint connector architecture.
- Incremental GitHub ingestion based on Git/blob version information.
- Local LLM/Ollama support and Amazon Bedrock provider support.
- Administrative controls, security controls, evaluation, benchmarking, and operational tooling.

### Important distinction

The current implementation should be described as **Hybrid RAG + structure-aware code intelligence**. It is not yet a complete persistent GraphRAG implementation.

## 3. Target Graph-of-AST architecture

The next architectural layer is a canonical graph built from parsed source structures and connected knowledge sources.

```text
Repository
  |
  +-- Directory
  |
  +-- File
       |
       +-- Class
       |    +-- Method
       |    +-- Method
       |
       +-- Function
       +-- API
       +-- Configuration
       +-- Test

Documentation
  +-- Page
  +-- Section
  +-- Runbook
  +-- Requirement

Business Knowledge
  +-- Capability
  +-- Service
  +-- Domain
```

### Core relationships

```text
CONTAINS
DEFINES
IMPORTS
CALLS
IMPLEMENTS
INHERITS
DEPENDS_ON
TESTED_BY
DOCUMENTED_BY
RELATED_TO
CHANGED_BY
```

The graph should preserve source identifiers and provenance so every important relationship can be traced back to the originating file, document, commit, or external system.

## 4. Implementation phases

### Phase 1 — Canonical AST model

Create a language-independent representation for parsed code entities.

Required entity types:

- Repository
- Directory
- File
- Module
- Class
- Method
- Function
- Variable
- Import
- API/endpoint
- Test

Each entity should retain:

- stable ID
- source ID
- repository
- file path
- symbol name
- qualified name
- language
- start/end location
- parent entity
- content hash
- parser metadata

### Phase 2 — Persistent Knowledge Graph

Introduce a graph store abstraction that can initially run locally and later map to a production graph database.

The abstraction should support:

- upsert node
- upsert edge
- delete node
- delete edge
- lookup by ID
- lookup by type
- neighborhood traversal
- relationship filtering
- provenance lookup

A local JSON/SQLite-backed implementation can be used for development. The interface should not couple application logic to a particular production database.

### Phase 3 — AST-to-graph builder

Transform parsed source structures into graph nodes and relationships.

Examples:

```text
File -> DEFINES -> Class
Class -> DEFINES -> Method
File -> IMPORTS -> Module
Method -> CALLS -> Function
Class -> IMPLEMENTS -> Interface
Test -> TESTED_BY/TESTS -> Function
```

The builder must be incremental. If a file has not changed, its graph representation should not be rebuilt.

### Phase 4 — Cross-source knowledge linking

Connect code to enterprise knowledge sources.

Examples:

```text
Service -> DOCUMENTED_BY -> Confluence Page
API -> DOCUMENTED_BY -> API Documentation
Requirement -> RELATED_TO -> Function
Runbook -> RELATED_TO -> Service
Capability -> DEPENDS_ON -> Service
```

Linking should combine deterministic signals and semantic similarity rather than relying on embeddings alone.

### Phase 5 — Git and temporal intelligence

Represent change history as first-class metadata.

```text
Commit -> CHANGED -> File
Commit -> CHANGED -> Function
PullRequest -> CHANGED -> File
PullRequest -> IMPLEMENTED -> Requirement
Developer -> AUTHORED -> Commit
```

This enables questions such as:

- What changed recently?
- Which functions were affected by a PR?
- Who owns or frequently changes this area?
- Which documentation may now be stale?

### Phase 6 — Graph-aware retrieval

Extend the existing retrieval pipeline:

```text
Question
   |
   +--> Lexical retrieval
   +--> Vector retrieval
   +--> Symbol retrieval
   +--> Graph retrieval
             |
             +--> neighborhood expansion
             +--> relationship traversal
             +--> dependency expansion
   |
   +--> RRF / fusion
   +--> reranking
   +--> security filtering
   +--> context construction
   +--> LLM generation
   +--> citations + confidence + trace
```

Graph retrieval should be used when the question contains relationship intent such as:

- depends on
- calls
- imports
- implements
- affected by
- related to
- changed by
- owned by

### Phase 7 — Impact and blast-radius analysis

Add graph queries that calculate affected entities from a starting node.

Example:

```text
Changed Function
      |
      +--> CALLS
      +--> DEPENDS_ON
      +--> TESTED_BY
      +--> DOCUMENTED_BY
      +--> CHANGED_BY
             |
             v
        Impact Set
```

The result should distinguish direct and transitive impact and provide evidence for every affected item.

### Phase 8 — CFG and data-flow intelligence

After the AST/KG foundation is stable, add deeper program analysis:

- control-flow graphs
- data-flow relationships
- taint-style propagation where appropriate
- variable definitions and uses
- exception/control branches
- inter-procedural call relationships

This should be introduced after the canonical graph model because CFG/data-flow entities will depend on stable symbol identity.

## 5. Incremental ingestion requirements

Incremental processing is a core requirement, not an optimization.

Expected behavior:

### Initial ingestion

```text
scanned = N
added = N
changed = 0
unchanged = 0
 deleted = 0
chunks_updated = N
```

### No source changes

```text
scanned = N
added = 0
changed = 0
unchanged = N
deleted = 0
chunks_updated = 0
```

### One changed file

```text
scanned = N
added = 0
changed = 1
unchanged = N-1
deleted = 0
chunks_updated = <chunks for changed file>
```

For GitHub, the source manifest should use Git tree/blob SHA as the authoritative item version. The manifest must be independent of the generated chunk list so an item remains detectable even if it currently produces zero chunks.

Deleted items must remove their associated chunks, embeddings, and graph entities.

## 6. Storage model

The architecture should keep these concerns separate:

| Store | Responsibility |
|---|---|
| Source manifest | Source version/delta detection |
| Document/chunk store | Searchable source content |
| Vector index | Semantic similarity |
| Lexical index | Exact/keyword retrieval |
| Symbol index | Code symbol retrieval |
| Knowledge Graph | Entities and relationships |
| Evaluation store | Benchmark/evaluation results |
| Audit store | Security/admin events |

This separation makes it possible to evolve each storage technology independently.

## 7. Security requirements

Graph retrieval must enforce the same authorization boundaries as normal retrieval.

A graph traversal must never expose a node or relationship merely because another connected node is visible.

Authorization should therefore be applied to:

1. graph nodes
2. graph edges where necessary
3. retrieved source content
4. generated context
5. citations

Tenant boundaries must remain intact across graph traversal.

## 8. Quality and evaluation

AST/KG features should be measured with dedicated tests and benchmarks.

### Structural extraction

- entity extraction accuracy
- symbol identity stability
- import resolution
- call relationship accuracy
- inheritance/implementation accuracy

### Retrieval

- Recall@K
- MRR
- nDCG
- graph traversal precision
- hybrid retrieval uplift

### Answer quality

- citation correctness
- claim coverage
- groundedness
- confidence calibration
- impact-analysis accuracy

### Incremental ingestion

- unchanged-source skip rate
- changed-item precision
- deleted-item cleanup
- ingestion latency
- API calls saved

## 9. Product capabilities enabled

Once the graph layer is implemented, Knowledge Fabric can expose higher-value enterprise workflows:

- "What calls this function?"
- "What will be affected if I change this API?"
- "Show the dependency chain for this service."
- "Which documentation describes this implementation?"
- "Which PRs changed this behavior?"
- "What tests cover this code path?"
- "Which business capabilities depend on this service?"
- "What documentation may be stale after this change?"
- "Explain this subsystem and show the evidence."

## 10. Definition of done for GraphRAG

The AST + KG initiative should be considered complete only when Knowledge Fabric has all of the following:

- [ ] Canonical AST entity model
- [ ] Persistent graph storage abstraction
- [ ] AST-to-graph builder
- [ ] Stable symbol/entity identity
- [ ] File/class/function/method relationships
- [ ] Import and dependency relationships
- [ ] Call relationships
- [ ] Code-to-document links
- [ ] Git/PR temporal relationships
- [ ] Incremental graph updates
- [ ] Graph query tools
- [ ] Graph-aware retrieval
- [ ] Vector + graph fusion
- [ ] Graph-aware reranking
- [ ] Blast-radius/impact analysis
- [ ] Graph-aware citations and provenance
- [ ] Tenant/ACL enforcement during graph traversal
- [ ] Evaluation suite for graph extraction and retrieval
- [ ] Production observability and failure handling

## 11. Product positioning

The strategic distinction is important:

> **Basic RAG retrieves chunks. Knowledge Fabric builds a connected model of enterprise knowledge and software structure.**

The near-term architecture should therefore evolve in controlled stages rather than prematurely introducing a graph database without stable entity identity, provenance, incremental updates, and security semantics.

The existing hybrid RAG and structure-aware code intelligence remain the retrieval foundation while the Graph-of-AST layer is introduced incrementally.
