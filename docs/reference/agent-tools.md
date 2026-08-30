# Agent tool reference

| Tool | Input | Output | Typical use |
|---|---|---|---|
| `search` | query, optional top_k | ranked chunks | broad evidence retrieval |
| `get_document` | item_id | all chunks for item | exact document context |
| `find_symbol` | symbol | matching code chunks | code intelligence |
| `get_related` | item_id | related chunks | neighborhood discovery |
| `compare_documents` | two item IDs | two document bodies | comparison |

Tools are deliberately explicit. This creates a stable boundary for future function-calling models and makes tool use testable without an LLM.
