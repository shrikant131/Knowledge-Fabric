"""Amazon Bedrock generation backend."""
from __future__ import annotations
import json

# Claude 3.5 Sonnet v2 reached EOL on 2026-07-30. Use a current global
# inference profile by default so a fresh Knowledge Fabric install does not
# report a stale model as unavailable.
DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"


class BedrockGenerator:
    def __init__(self, model_id=DEFAULT_MODEL_ID, region_name="us-east-1"):
        import boto3
        self.region_name = region_name
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.model_id = model_id
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        self.last_error = None

    def health(self):
        """Cheap credential-chain check; does not make a billable model call."""
        try:
            import boto3
            session = boto3.Session(region_name=self.region_name)
            creds = session.get_credentials()
            return bool(creds and getattr(creds, "access_key", None))
        except Exception:
            return False

    def health_details(self):
        """Return diagnostics suitable for the admin console without exposing secrets."""
        try:
            import boto3
            session = boto3.Session(region_name=self.region_name)
            creds = session.get_credentials()
            if not creds or not getattr(creds, "access_key", None):
                return {"ready": False, "credentials": False, "region": self.region_name,
                        "model": self.model_id, "error": "AWS credentials were not found by boto3."}
            return {"ready": True, "credentials": True, "region": self.region_name,
                    "model": self.model_id, "error": None}
        except Exception as exc:
            return {"ready": False, "credentials": False, "region": self.region_name,
                    "model": self.model_id, "error": str(exc)}

    def probe(self):
        """Perform a real, minimal Bedrock invocation and surface useful errors."""
        try:
            text = self.generate("Reply with OK only.", "OK", max_tokens=8)
            return bool(text.strip())
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def generate(self, system_prompt, user_prompt, max_tokens=800):
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        })
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                accept="application/json",
                contentType="application/json",
            )
            payload = json.loads(response["body"].read())
        except Exception as exc:
            self.last_error = str(exc)
            raise
        usage = payload.get("usage") or {}
        self.last_usage = {
            "input_tokens": int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(usage.get("output_tokens", 0) or 0),
        }
        content = payload.get("content") or []
        if not content or not content[0].get("text"):
            raise RuntimeError("Bedrock returned an empty response")
        self.last_error = None
        return content[0]["text"]
