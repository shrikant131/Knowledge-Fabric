# Knowledge Fabric — Full-Stack POC

Knowledge Fabric is a local-first, multi-source enterprise knowledge platform with hybrid RAG, agent tools, code intelligence, corrective retrieval, reranking, citations, confidence, evaluation, continuous ingestion and an optional real LLM.

## Product principles

- **Works immediately:** local TF-IDF + numpy vector search + lexical search + deterministic generator. No API key required.
- **LLM is a switch:** enable Bedrock or OpenAI-compatible generation from the UI. The retrieval/agent architecture stays the same.
- **Evidence first:** answers carry source citations, retrieval traces and confidence signals.
- **Secure by design:** sensitivity filtering happens before context reaches generation.
- **Operational:** source registry, delta ingestion, scheduler/webhooks, status, query logs and regression evaluation are included.

## Quick start

```bash
python -m venv .venv
# activate the environment
pip install -r requirements.txt
./start.sh
```

Open `http://localhost:5050`.

The first start indexes `sample_data/` and launches the control plane. FAISS and rank_bm25 are optional accelerators; the product includes fallbacks so installation does not depend on native wheels.


## Documentation

Start with **[START_HERE.md](START_HERE.md)**. The full documentation is under `docs/` and follows a tutorial / how-to / reference / explanation structure.

- [Documentation home](docs/index.md)
- [5-minute quickstart](docs/tutorials/quickstart.md)
- [Enable LLM](docs/how-to/enable-llm.md)
- [Add a source](docs/how-to/add-source.md)
- [Tune RAG](docs/how-to/tune-rag.md)
- [Live GitHub + LLM smoke test](docs/how-to/live-github-llm-test.md)
- [Architecture](docs/architecture/overview.md)
- [API reference](docs/reference/api.md)
- [Troubleshooting](docs/operations/troubleshooting.md)
- [Security model](docs/security/security-model.md)
- [Contributing](docs/CONTRIBUTING.md)

To build a local documentation site if MkDocs Material is installed:

```bash
pip install mkdocs-material
mkdocs serve
```

## LLM switch

Open **Settings** for a source and choose:

- **OFF — local:** zero LLM/API calls.
- **ON — Amazon Bedrock:** uses the normal AWS credential chain and configured Bedrock model.
- **ON — OpenAI-compatible:** uses `OPENAI_API_KEY` and the configured model.

The API also exposes:

```http
POST /api/sources/<source_id>/llm
{"enabled": true, "provider": "bedrock"}
```

If provider credentials are missing, the application reports the error and remains usable in local mode.

## Agent and RAG capabilities

### Retrieval

- lexical BM25 (rank_bm25 when installed, dependency-free BM25 fallback otherwise)
- TF-IDF local vector retrieval
- optional Bedrock embeddings
- symbol-aware code retrieval
- reciprocal-rank fusion
- deterministic cross-style reranking
- metadata/sensitivity filtering
- query decomposition and corrective retrieval
- semantic cache with content-hash invalidation

### Agent tools

The `KnowledgeFabricAgent` exposes:

- `search(query)`
- `get_document(item_id)`
- `find_symbol(symbol)`
- `get_related(item_id)`
- `compare_documents(a, b)`

This is intentionally an explicit tool boundary so a future function-calling model can select tools without coupling the model to storage internals.

### Evidence and trust

Every answer can expose:

- citations
- previews
- retrieval scores
- cache state
- corrective rounds
- agent/retrieval trace
- confidence score and label
- groundedness proxy
- low-evidence behavior / no-guess instruction

### Sources

Current connectors:

- local filesystem: Python, Java, Markdown, text and PDF
- Confluence REST polling
- SharePoint Graph delta polling

The connector interface is intentionally isolated; GitHub public-repository ingestion is now included, while S3, Jira, Slack or database connectors can be added without changing retrieval or generation.

### Continuous ingestion

```bash
python -m knowledge_fabric.cli watch --interval 30 --config manifest.yaml
python -m knowledge_fabric.cli serve-webhook --port 8787 --secret dev-secret --config manifest.yaml
```

The admin control plane can start/stop registered sources and trigger manual synchronization.

### Evaluation

```bash
python -m knowledge_fabric.cli evaluate --golden golden_dataset/sample_data.yaml --config manifest.yaml
python -m knowledge_fabric.cli fairness --config manifest.yaml
```

The regression runner measures retrieval precision/recall and groundedness. Query logs are append-only JSONL and can be used for operational analytics.

## Architecture

```text
Sources → Connectors → Parse/Chunk → Embed → Knowledge Store
                                             ↓
Question → Router → Agent/Query Plan → Hybrid Retrieval → RRF → Reranker
                                             ↓
                                   Context + Security Filter
                                             ↓
                               Local Generator OR Real LLM
                                             ↓
                         Answer + Citations + Confidence + Trace
```

## Configuration

`manifest.yaml` controls source and pipeline defaults. Per-source manifests created by the UI live under `connectors_registry/`.

Important settings include:

- `llm_enabled`
- `llm_provider`
- `embedder`
- `top_k`
- `enable_reranker`
- `enable_query_expansion`
- `enable_self_rag`
- `allowed_sensitivity`
- `confidence_threshold`

## Production evolution

The interfaces are deliberately ready for replacing local components with production services:

- FAISS/numpy → OpenSearch Serverless or pgvector
- TF-IDF → Titan/OpenAI/local embedding model
- local reranker → cross-encoder service
- JSON status → PostgreSQL/Redis
- scheduler threads → EventBridge/SQS/Step Functions
- file connector → GitHub/S3/Jira/Slack connectors
- local auth policy → enterprise IAM/ACL service
- Flask UI → SSO-enabled enterprise frontend

The POC does not pretend these production services are present locally; it provides clean seams for them.

## Zero-Docker local install

Knowledge Fabric can be installed directly with Python; Docker is optional.

```bash
python3 local_install.py
source .venv/bin/activate
kf start
```

Windows PowerShell:

```powershell
python .\local_install.py
.\.venv\Scripts\Activate.ps1
kf start
```

Then open the browser Playground. See `docs/operations/local-python.md` for details and `deploy/` for cloud deployment starters.
