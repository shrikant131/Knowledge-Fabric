# Admin Control Plane

The Admin Console is the operational center of Knowledge Fabric.

## Sections

### Overview
System health, sources, indexing, active jobs, LLM readiness.

### AI & Models
- LLM on/off
- provider
- model
- temperature
- token limit
- generation readiness
- model test

### Retrieval
- hybrid retrieval
- BM25
- vector search
- symbol search
- top-K
- reranking
- query expansion
- corrective retrieval
- cache

### Agent & Tools
- agent mode
- available tools
- maximum steps
- tool permissions
- memory/planning controls

### Knowledge
- knowledge bases
- sources
- documents
- versions
- metadata
- index health

### Connectors
- GitHub
- local files
- future enterprise connectors

### Ingestion
- sync status
- jobs
- failures
- retries
- scheduled sync

### Security
- authentication mode
- roles
- source permissions
- audit

### Evaluation
- Live Test Lab
- Benchmark Studio
- golden datasets
- regression tests

### Observability
- requests
- latency
- retrieval metrics
- LLM usage
- errors
- cost

## Configuration safety

Configuration changes should be:

1. validated
2. persisted
3. versioned
4. audited

Secrets should never be displayed back through normal configuration APIs.
