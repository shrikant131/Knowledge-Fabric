# AWS deployment

## Fastest current POC: EC2

Use a small **Free Tier/credit-eligible** EC2 instance, install Python, and run Knowledge Fabric without Docker.

1. Launch Amazon Linux.
2. Attach an IAM instance role with only the Bedrock permissions required.
3. Copy this repository to the instance.
4. Create a virtual environment and install with `pip install -e .`.
5. Set `KF_HOST=127.0.0.1`, `KF_AUTH_MODE=api_key`, a strong `ADMIN_API_KEY`, and a strong `SECRET_KEY`.
6. Put nginx or an ALB in front of the app for HTTPS.
7. Enable Bedrock model access in the target region/account.
8. Open `/playground` and test the model from Admin → AI & Models.

Do not store AWS access keys on the EC2 host. boto3 should use the instance role.

## Production cloud target

For a horizontally scalable deployment:

```text
ALB
 |
ECS/Fargate API
 |
SQS -> ingestion/evaluation workers
 |
S3 + PostgreSQL + managed vector/search backend
 |
Bedrock
```

The current repository also contains an ECS task-definition starter. Before scaling beyond one instance, move authoritative metadata, artifacts, indexes and job state out of local disk.

## Cost warning

Free-tier/credit eligibility is account- and service-dependent. Bedrock inference is usage-based. Start with small benchmark sets and configure billing alerts.
