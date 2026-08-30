# Enable LLM generation

Knowledge Fabric is local-first: LLM generation is optional. Turning it off must never require a different application build.

## Amazon Bedrock

1. Configure AWS credentials using the normal AWS credential chain.
2. Set the Bedrock region and model in the source settings or YAML.
3. Set `llm_provider: bedrock`.
4. Set `llm_enabled: true`.
5. Set `generator: bedrock`.
6. Restart the application or save the source settings.
7. Confirm the source dashboard shows **LLM ON · bedrock**.

Example:

```yaml
llm_enabled: true
llm_provider: bedrock
generator: bedrock
bedrock_region: us-east-1
bedrock_chat_model: anthropic.claude-3-5-sonnet-20241022-v2:0
```

## OpenAI-compatible provider

Set the API key in the environment, not in YAML:

```bash
export OPENAI_API_KEY="..."
```

Then configure:

```yaml
llm_enabled: true
llm_provider: openai
generator: openai
openai_chat_model: gpt-4.1-mini
```

## Verify provider health

The UI validates the provider when the LLM setting is changed. The API endpoint is:

```http
POST /api/sources/<source_id>/llm
Content-Type: application/json

{"enabled": true, "provider": "bedrock"}
```

If validation fails, the product remains usable in local mode. Do not paste credentials into manifests or source control.
