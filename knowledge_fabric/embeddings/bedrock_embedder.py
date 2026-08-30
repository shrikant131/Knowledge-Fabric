"""Amazon Bedrock embeddings backend.

Requires AWS credentials with bedrock:InvokeModel permission and access to
the target embedding model enabled in your account/region. Not runnable in
this sandbox (no AWS network egress) -- this is what you point the pilot at
once you run it in your own AWS environment.
"""
from __future__ import annotations

import json

import numpy as np

from knowledge_fabric.embeddings.base import Embedder

DEFAULT_MODEL_ID = "amazon.titan-embed-text-v2:0"
TITAN_V2_DIMENSION = 1024


class BedrockEmbedder(Embedder):
    def __init__(self, model_id: str = DEFAULT_MODEL_ID, region_name: str = "us-east-1"):
        import boto3  # imported lazily so the rest of the package works without boto3 configured

        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.model_id = model_id
        self.dimension = TITAN_V2_DIMENSION

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            body = json.dumps({"inputText": text})
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                accept="application/json",
                contentType="application/json",
            )
            payload = json.loads(response["body"].read())
            vectors.append(payload["embedding"])
        return np.array(vectors, dtype="float32")
