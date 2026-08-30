"""Amazon Bedrock generation backend."""
from __future__ import annotations
import json

DEFAULT_MODEL_ID="anthropic.claude-3-5-sonnet-20241022-v2:0"

class BedrockGenerator:
    def __init__(self, model_id=DEFAULT_MODEL_ID, region_name="us-east-1"):
        import boto3
        self.region_name=region_name
        self.client=boto3.client("bedrock-runtime",region_name=region_name)
        self.model_id=model_id
        self.last_usage={"input_tokens":0,"output_tokens":0}

    def health(self):
        # Do not require environment credentials: boto3 resolves EC2/ECS role,
        # web identity, profile and environment credentials through its chain.
        try:
            import boto3
            creds=boto3.Session(region_name=self.region_name).get_credentials()
            return bool(creds and getattr(creds,"access_key",None))
        except Exception:
            return False

    def probe(self):
        text=self.generate("Reply with OK only.","OK",max_tokens=8)
        return bool(text.strip())

    def generate(self,system_prompt,user_prompt,max_tokens=800):
        body=json.dumps({"anthropic_version":"bedrock-2023-05-31","max_tokens":max_tokens,
                         "system":system_prompt,"messages":[{"role":"user","content":user_prompt}]})
        response=self.client.invoke_model(modelId=self.model_id,body=body,accept="application/json",contentType="application/json")
        payload=json.loads(response["body"].read())
        usage=payload.get("usage") or {}
        self.last_usage={"input_tokens":int(usage.get("input_tokens",0) or 0),
                         "output_tokens":int(usage.get("output_tokens",0) or 0)}
        return payload["content"][0]["text"]
