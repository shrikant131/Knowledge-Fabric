# Secrets management

Never commit API keys, bearer tokens or passwords to manifests.

Use environment variables for the POC:

```bash
export OPENAI_API_KEY="..."
export AWS_PROFILE="..."
```

Production should use a managed secret store and short-lived credentials where possible.
