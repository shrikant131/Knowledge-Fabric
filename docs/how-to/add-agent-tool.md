# Add an agent tool

Agent tools are explicit Python capabilities. The model should not receive direct access to storage internals.

## 1. Add a method to `KnowledgeToolRegistry`

```python
class KnowledgeToolRegistry:
    def get_owner(self, item_id):
        ...
```

Return structured data rather than prompt-formatted prose.

## 2. Expose the capability through the agent

The agent should decide when the capability is useful. Keep planning separate from tool execution.

## 3. Add a test

Test:

- valid input
- missing item
- empty result
- sensitivity filtering
- deterministic output where possible

## 4. Add documentation

Update the tool table in `docs/reference/agent-tools.md` and add a how-to guide if the capability is user-facing.
