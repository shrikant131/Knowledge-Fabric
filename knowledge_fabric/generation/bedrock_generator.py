"""Amazon Bedrock generation backend."""
from __future__ import annotations
import os

DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_API_KEY_ENV = "AWS_BEARER_TOKEN_BEDROCK"


class BedrockGenerator:
    def __init__(self, model_id=DEFAULT_MODEL_ID, region_name=None, api_key_env=DEFAULT_API_KEY_ENV):
        import boto3
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        self.model_id = model_id
        self.api_key_env = api_key_env
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        self.last_error = None

    def _has_bearer_key(self):
        return bool(os.getenv(self.api_key_env))

    def _has_aws_credentials(self):
        try:
            import boto3
            session = boto3.Session(region_name=self.region_name)
            creds = session.get_credentials()
            return bool(creds and getattr(creds, "access_key", None))
        except Exception:
            return False

    def health(self):
        return self._has_bearer_key() or self._has_aws_credentials()

    def health_details(self):
        bearer = self._has_bearer_key()
        iam = self._has_aws_credentials()
        return {
            "ready": bearer or iam,
            "credentials": bearer or iam,
            "bearer_token": bearer,
            "aws_credentials": iam,
            "credential_source": self.api_key_env if bearer else ("aws-shared-credentials-or-role" if iam else None),
            "region": self.region_name,
            "model": self.model_id,
            "error": None if (bearer or iam) else "No Bedrock bearer API key or AWS credentials were found.",
        }

    def probe(self):
        try:
            text = self.generate("Reply with OK only.", "OK", max_tokens=8)
            return bool(text.strip())
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def generate(self, system_prompt, user_prompt, max_tokens=800):
        try:
            response = self.client.converse(
                modelId=self.model_id,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                inferenceConfig={"maxTokens": max_tokens},
            )
        except Exception as exc:
            self.last_error = str(exc)
            raise
        usage = response.get("usage") or {}
        self.last_usage = {
            "input_tokens": int(usage.get("inputTokens", 0) or 0),
            "output_tokens": int(usage.get("outputTokens", 0) or 0),
        }
        content = (response.get("output") or {}).get("message", {}).get("content") or []
        text = next((part.get("text") for part in content if part.get("text")), None)
        if not text:
            raise RuntimeError("Bedrock returned an empty response")
        self.last_error = None
        return text
