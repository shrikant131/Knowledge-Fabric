# Cloud architecture and local/cloud parity

The same application code runs locally and in a container. Local mode uses the filesystem and local embeddings; cloud mode can use Bedrock/OpenAI and managed infrastructure.

## Local

`Python -> Flask -> filesystem indexes -> local embedding -> optional LLM`

## Cloud POC

`ALB/managed ingress -> container -> persistent volume -> Bedrock/OpenAI`

## Production target

`Ingress -> stateless API -> worker queue -> S3 + PostgreSQL + OpenSearch -> Bedrock`

The repository deliberately keeps the application layer provider-agnostic so the local Python experience remains simple while the cloud deployment can progressively replace local stores with managed adapters.
