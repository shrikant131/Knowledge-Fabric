# AWS ECS/Fargate deployment

1. Build and push the existing `Dockerfile` to ECR.
2. Create an ECS Fargate service behind an Application Load Balancer.
3. Use `deploy/aws/ecs/task-definition.template.json` as the starting task definition.
4. Put `ADMIN_API_KEY`, `OPENAI_API_KEY`, and any AWS/GitHub secrets in AWS Secrets Manager and reference them from the task definition.
5. Attach an EFS volume at `/data` for the single-service POC, or replace the local stores with managed S3/Postgres/OpenSearch adapters before multi-task scaling.
6. Give the task an IAM role permitting only the required Bedrock/S3 operations.

For a one-command-ish managed container demo, use the App Runner assets in `deploy/aws/app-runner`.
