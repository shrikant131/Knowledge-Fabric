# Agent architecture

The agent is intentionally deterministic-capable. It can plan and use tools without requiring an LLM.

This provides two important properties:

- the product remains useful when LLM access is unavailable;
- tool behavior can be regression-tested independently of model behavior.

A future function-calling model can replace or enrich the planner while retaining the same tool contract.
