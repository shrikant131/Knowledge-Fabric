# AST + Knowledge Graph Implementation Plan

**Project:** Knowledge Fabric  
**Branch:** `main`  
**Status:** Current architecture + target Graph-of-AST roadmap

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

## 2. Current product architecture

Knowledge Fabric is currently a **local-first enterprise knowledge platform** with a web Admin Console, ingestion pipeline, hybrid retrieval engine, agent/tool layer, multiple LLM providers, evaluation tooling, and deployment paths for local Python and AWS.

### 2.1 High-level architecture

```text
                         Knowledge Fabric
                                |
        +-----------------------+-----------------------+
        |                       |                       |
   Source Connectors       Admin / UX              Providers
        |                       |                       |
   +----+----+----+       +----+----+----+        +----+----+----+
   |         |    |       |         |    |        |         |    |
 GitHub   Files Confluence SharePoint  Console Playground  Local/Ollama
   |         |    |       |         |    |        Bedrock  OpenAI-compatible
   +---------+----+-------+---------+----+
                         |
                    Ingestion Pipeline
                         |
          +--------------+---------------+
          |              |               |
       Parsing        Chunking        Metadata
          |              |               |
          +--------------+---------------+
                         |
              +----------+----------+
              |                     |
        Lexical Index         Vector Index
              |                     |
        Symbol Index                |
              +----------+----------+
                         |
                 Hybrid Retrieval
                         |
              RRF + Reranking + Cache
                         |
                  Security Filter
                         |
                    Agent / Tools
                         |
                 LLM Generation
                         |
             Citations + Confidence
                    + Decision Trace
```

### 2.2 User-facing application surfaces

#### Admin Console

The Admin Console is the operational control plane. It is responsible for:

- provider configuration and readiness checks
- model and region configuration
- environment/credential status
- source connector configuration
- ingestion and scheduler controls
- security configuration
- tenant-aware administration
- audit visibility
- operational diagnostics

Provider readiness should distinguish **configuration**, **credential availability**, and **successful live model connectivity**. AWS SDK credential-chain authentication must be recognized in addition to explicit environment variables.

#### Playground

The Playground is the primary interactive knowledge-query experience. It exercises the real retrieval and generation path and is intended for exploratory questions, evidence inspection, and validation of answers.

The response model is designed to expose:

- answer
- supporting sources/citations
- confidence diagnostics
- retrieval/decision trace
- provider/model information where applicable

#### Quick Start

Quick Start provides the guided path for getting a local Knowledge Fabric instance running, configuring a source, selecting a provider, ingesting knowledge, and executing the first query.

#### Live Test Lab

Live Test Lab provides an operational way to execute representative queries against the configured system and inspect retrieval/generation behavior. It is intended for rapid provider, connector, and pipeline validation.

#### Benchmark Studio

Benchmark Studio provides evaluation workflows for retrieval and answer quality, including repeatable benchmark cases and metrics. It is the foundation for measuring changes to retrieval, reranking, generation, and—later—the knowledge graph.

## 3. Current source and ingestion architecture

Knowledge Fabric has connector abstractions for:

- GitHub repositories
- local files
- Confluence
- SharePoint

The ingestion path is:

```text
Source
  -> Connector
  -> Source identity/version
  -> Parse
  -> Structure-aware chunking
  -> Metadata
  -> Embedding
  -> Lexical/vector/symbol indexes
```

### Incremental ingestion

Incremental processing is a core requirement, not an optimization.

For GitHub, the authoritative version signal should be the Git tree/blob SHA rather than a generated chunk hash. A persistent source manifest must remain independent of the generated chunk list.

Expected behavior:

```text
Initial ingestion:
  scanned=N
  added=N
  changed=0
  unchanged=0
  deleted=0
  chunks_updated=N

No source changes:
  scanned=N
  added=0
  changed=0
  unchanged=N
  deleted=0
  chunks_updated=0

One changed file:
  scanned=N
  added=0
  changed=1
  unchanged=N-1
  deleted=0
  chunks_updated=<chunks for changed file>
```

A changed or deleted item must update/remove its old chunks, embeddings, and—once the KG is implemented—its graph entities and relationships.

## 4. Current retrieval architecture

The current retrieval stack is deliberately multi-signal rather than vector-only.

```text
Question
   |
   +--> Query routing / intent
   |
   +--> Query expansion / corrective retrieval
   |
   +--> Lexical retrieval
   +--> Vector retrieval
   +--> Symbol retrieval
   |
   +--> Reciprocal Rank Fusion (RRF)
   |
   +--> Reranking
   |
   +--> Semantic cache where applicable
   |
   +--> Security / tenant filtering
   |
   +--> Context construction
   |
   +--> Agent / tool execution
   |
   +--> LLM generation
   |
   +--> Citations + confidence + decision trace
```

This provides a stronger foundation for developer questions than pure document similarity because code symbols and lexical matches can contribute directly to retrieval.

### Current code intelligence

The code chunking layer is structure-aware and uses AST/tree-sitter support where available, with a structured fallback parser. Current capabilities include function/class-oriented chunks and symbol-aware retrieval.

This is an **AST-aware retrieval foundation**, not yet a complete persisted AST graph.

## 5. Current LLM/provider architecture

Knowledge Fabric is designed to support multiple generation modes:

### Local / deterministic fallback

A local no-LLM mode exists for deterministic development and environments where no model service is configured. This should not be confused with a local generative model.

### Local Ollama

The application supports an actual local LLM through Ollama. The configured local model/base URL are treated as a provider and should have a live connectivity check in the Admin Console.

Typical local architecture:

```text
Knowledge Fabric -> http://127.0.0.1:11434 -> Ollama -> Local model
```

### Amazon Bedrock

Bedrock is a first-class generation provider. The implementation should support both:

- Bedrock bearer/API-key authentication via `AWS_BEARER_TOKEN_BEDROCK`
- normal AWS SDK credential-chain authentication, including shared AWS credentials and workload roles

Provider readiness should perform a real model probe and report the configured model, region, authentication mode, and actionable failure reason.

The current target Claude Haiku 4.5 model configuration is:

```yaml
llm_provider: bedrock
generator: bedrock
bedrock_chat_model: global.anthropic.claude-haiku-4-5-20251001-v1:0
bedrock_api_key_env: AWS_BEARER_TOKEN_BEDROCK
```

### OpenAI-compatible provider

An OpenAI-compatible generation path is retained so Knowledge Fabric can connect to compatible hosted or self-managed inference endpoints.

## 6. Current agent and tool architecture

The agent layer is intentionally explicit rather than allowing arbitrary tool execution.

```text
User question
    |
 Agent / query planner
    |
    +--> Retrieval tools
    +--> Symbol/code intelligence
    +--> Source/context tools
    +--> Evaluation/diagnostic tools
    |
 Context + evidence
    |
 Provider-backed generation
```

Tools should have explicit registration, input validation, authorization boundaries, and observable execution traces.

This architecture is the bridge from traditional RAG toward a more capable enterprise agent platform.

## 7. Current security architecture

Security is applied across the request, retrieval, administration, and ingestion surfaces.

Current controls include:

- optional API-key authentication
- CSRF protection
- security headers
- rate limiting
- optional Redis-backed rate limiting
- upload size/type validation
- source ID validation
- tenant-aware principals
- sensitivity/authorization filtering
- audit/admin configuration persistence

The target architecture must extend these boundaries into graph traversal. A graph edge must never become an authorization bypass merely because a connected node is visible.

## 8. Current persistence/storage model

The application keeps distinct concerns separated so individual technologies can evolve independently.

| Store/component | Current responsibility |
|---|---|
| Source state/manifest | Source version and incremental-delta detection |
| Document/chunk store | Searchable source content |
| Vector index | Semantic similarity |
| Lexical index | Exact/keyword retrieval |
| Symbol index | Code symbol retrieval |
| Semantic cache | Reuse of compatible query results |
| Evaluation/benchmark state | Quality measurement |
| Audit/config state | Administration and operational records |
| Knowledge Graph | Target architecture; not yet the full production graph layer |

Local persistence is intended to make the platform runnable without a cloud dependency while preserving clean seams for production storage.

## 9. Current deployment architecture

### Local Python

The primary development path is a Python virtual environment with the application, connectors, indexes, and local provider integrations running on the developer workstation.

```text
Browser
  -> Knowledge Fabric web app
       -> local persistence/indexes
       -> Ollama (optional)
       -> AWS Bedrock (optional)
       -> external knowledge sources
```

### AWS

The repository also contains deployment starters for AWS. The architecture is intended to support a simple single-node deployment for a POC and a path toward horizontally scalable services.

The long-term shape is:

```text
Internet / corporate network
          |
      Load balancer
          |
   Knowledge Fabric API
          |
   +------+-------+----------------+
   |              |                |
 Persistent     Queue/jobs     Retrieval/graph
 storage         workers          services
   |              |                |
   +--------------+----------------+
                  |
          Bedrock / enterprise sources
```

For production, identity should use workload IAM roles rather than static AWS credentials, and persistence should be externalized as the deployment grows.

## 10. Important current-vs-target distinction

The current implementation should be described as:

> **Hybrid RAG + structure-aware code intelligence**

It is **not yet a complete persistent GraphRAG implementation**.

What exists today:

- structure-aware code parsing/chunking
- function/class-oriented retrieval
- lexical + vector + symbol retrieval
- RRF and reranking
- query expansion/corrective retrieval
- semantic cache
- citations, confidence, and decision traces
- enterprise source connector architecture
- incremental GitHub ingestion foundation
- local Ollama and Bedrock generation paths
- Admin Console, Playground, Quick Start, Live Test Lab, and Benchmark Studio
- security, administration, evaluation, and deployment foundations

What the Graph-of-AST initiative adds:

- canonical AST entities
- persistent graph nodes/edges
- stable symbol identity
- calls/imports/dependency relationships
- code-to-document relationships
- Git/PR temporal relationships
- graph retrieval
- vector + graph fusion
- blast-radius analysis
- graph-aware provenance and citations

## 11. Target Graph-of-AST architecture

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

## 12. Implementation phases

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
Test -> TESTS -> Function
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

## 13. Incremental ingestion requirements for the target architecture

Incremental processing must cover all representations:

```text
Source version change
       |
       +--> changed chunks only
       +--> changed embeddings only
       +--> changed lexical/symbol entries only
       +--> changed AST nodes only
       +--> changed graph edges only
       +--> deleted entities removed
```

For GitHub, the source manifest should use Git tree/blob SHA as the authoritative item version. The manifest must be independent of the generated chunk list so an item remains detectable even if it currently produces zero chunks.

## 14. Quality and evaluation

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

## 15. Security requirements for GraphRAG

Graph retrieval must enforce the same authorization boundaries as normal retrieval.

A graph traversal must never expose a node or relationship merely because another connected node is visible.

Authorization should therefore be applied to:

1. graph nodes
2. graph edges where necessary
3. retrieved source content
4. generated context
5. citations

Tenant boundaries must remain intact across graph traversal.

## 16. Product capabilities enabled by the graph

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

## 17. Definition of done for GraphRAG

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

## 18. Product positioning

The strategic distinction is important:

> **Basic RAG retrieves chunks. Knowledge Fabric builds a connected model of enterprise knowledge and software structure.**

The near-term architecture should therefore evolve in controlled stages rather than prematurely introducing a graph database without stable entity identity, provenance, incremental updates, and security semantics.

The existing hybrid RAG and structure-aware code intelligence remain the retrieval foundation while the Graph-of-AST layer is introduced incrementally.
