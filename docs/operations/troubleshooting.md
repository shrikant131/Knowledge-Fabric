# Troubleshooting

## The dashboard opens but no results appear

Run a manual sync and verify that the source reports indexed chunks.

```bash
python -m knowledge_fabric.cli ingest --config manifest.yaml
```

## Retrieval is empty

Check:

1. the source was indexed;
2. sensitivity policy permits the chunks;
3. the query is relevant to the sample corpus;
4. `top_k` is greater than zero;
5. the index directory is writable.

## LLM does not enable

The application can run with LLM OFF. If ON fails:

1. verify the provider setting;
2. verify credentials are available to the process;
3. verify the region/model;
4. inspect the provider health error;
5. return to local mode while diagnosing.

## Answers are weak

Inspect Evidence and Decision trace first. If the correct document is not retrieved, tune ingestion/retrieval. If the correct evidence is retrieved but the answer is wrong, inspect generation and groundedness.

## Evaluation fails

Do not immediately lower thresholds. First inspect which golden cases changed and whether the failure is retrieval, ranking, generation or dataset drift.
