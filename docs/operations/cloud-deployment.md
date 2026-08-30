# Cloud deployment

## Recommended for this product

For an AWS/Bedrock environment, use a container service rather than a personal laptop. AWS App Runner is the quickest managed web-service option; ECS on Fargate is the stronger production architecture when you need separate web, ingestion and benchmark workers. AWS documents Fargate as serverless infrastructure for ECS services/tasks.

For a simple cross-cloud deployment, Google Cloud Run or Azure Container Apps are also suitable because Knowledge Fabric already ships as a container. Both support managed HTTPS ingress and scaling without managing Kubernetes nodes.

### POC architecture

```text
Browser
  |
HTTPS
  v
Managed container service
  |
  +-- Knowledge Fabric web/admin
  +-- Live benchmark execution
  |
  +---> GitHub
  +---> OpenAI / Bedrock
```

### Production architecture

```text
                 HTTPS
                   |
              Load Balancer
                   |
          +--------+--------+
          |                 |
       Web/API          Worker queue
          |                 |
          |          +------+------+
          |          |             |
          v          v             v
       Config DB   Ingestion    Benchmark
          |          |             |
          +----------+-------------+
                     |
               Object storage
                     |
              Vector / Search DB
```

Do not rely on the container filesystem for durable production data. The current POC persists registry, audit and benchmark files locally; that is acceptable for a single-instance demonstration but must be externalized for multi-instance cloud deployment.

## Secrets

Use the cloud provider's secret manager / workload identity rather than committing API keys. For Bedrock on AWS, prefer an IAM role attached to the workload rather than static AWS access keys.

## Security

The Admin Console is an operational interface and should not be exposed publicly without authentication and authorization. Add SSO/IAM, source ACL enforcement, HTTPS-only ingress, audit retention and private networking before production use.
