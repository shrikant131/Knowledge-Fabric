# CLI reference

## Ingest

```bash
python -m knowledge_fabric.cli ingest --config manifest.yaml
```

## Query

```bash
python -m knowledge_fabric.cli query "How does retry work?" --config manifest.yaml
```

## Watch

```bash
python -m knowledge_fabric.cli watch --interval 30 --config manifest.yaml
```

## Webhook

```bash
python -m knowledge_fabric.cli serve-webhook --port 8787 --secret dev-secret --config manifest.yaml
```

## Evaluation

```bash
python -m knowledge_fabric.cli evaluate --golden golden_dataset/sample_data.yaml --config manifest.yaml
```

## Fairness/source-diversity audit

```bash
python -m knowledge_fabric.cli fairness --config manifest.yaml
```
