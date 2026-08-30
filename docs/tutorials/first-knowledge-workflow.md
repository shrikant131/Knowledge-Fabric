# First knowledge workflow

This tutorial walks through the complete product journey: source → ingestion → retrieval → answer → evaluation.

## 1. Register a source

From the dashboard select **Add source**. Start with `file` and point it at a directory containing Markdown, text, Python, Java or PDF files.

## 2. Sync

Click **Sync**. The ingestion pipeline discovers new and changed items, parses them, chunks them, embeds them and persists the index.

## 3. Query

Open the source and ask a question. Knowledge Fabric performs intent planning, hybrid retrieval, fusion and reranking before generation.

## 4. Inspect trust signals

Review:

- cited source and symbol
- retrieval score
- confidence label
- evidence coverage
- source agreement
- decision trace

## 5. Change the generation mode

Go to **Settings** and switch LLM from OFF to ON only when a configured provider is available. The retrieval flow remains unchanged.

## 6. Evaluate

Run the golden dataset after changing retrieval or generation settings. Treat evaluation failures as regression signals, not as something to hide.
