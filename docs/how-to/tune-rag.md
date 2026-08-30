# Tune retrieval and RAG quality

Tune retrieval in this order.

## 1. Verify ingestion

If the expected source is absent, tuning retrieval cannot fix the problem.

```bash
python -m knowledge_fabric.cli ingest --config manifest.yaml
```

## 2. Inspect the retrieved evidence

Use the query screen and compare the top results with the expected source.

## 3. Adjust Top K

`top_k` controls the initial evidence budget. Increasing it can improve recall but increases context and reranking work.

## 4. Enable reranking

`enable_reranker: true` adds a second-stage score after hybrid retrieval.

## 5. Enable query expansion

`enable_query_expansion: true` lets the deterministic agent split compound questions and retrieve evidence for each part.

## 6. Tune confidence carefully

`confidence_threshold` controls when the system should treat evidence as insufficient. Lowering it may increase answered queries while increasing unsupported-answer risk.

## 7. Run evaluation after every meaningful change

```bash
python -m knowledge_fabric.cli evaluate --golden golden_dataset/sample_data.yaml --config manifest.yaml
```

Do not optimize a single example at the expense of the regression set.
