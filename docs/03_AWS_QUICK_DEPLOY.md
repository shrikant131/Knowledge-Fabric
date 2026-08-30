# AWS Quick Deployment

## Recommended first deployment

For a low-cost proof of concept, use a single EC2 instance rather than starting with ECS, OpenSearch, queues, and multiple managed services.

This keeps the deployment simple while allowing Bedrock access through an IAM role.

## Architecture

```text
Internet
   |
EC2
   |
Knowledge Fabric
   |
Bedrock
```

## 1. Launch EC2

In AWS Console → EC2 → Launch Instance.

For a POC, select an instance marked **Free tier eligible** in your account.

Use Amazon Linux and a modest root volume. Exact free-tier eligibility depends on account age, plan, region, and usage.

## 2. Create IAM role

Attach an EC2 role that permits only the Bedrock actions required by the selected models.

Do not put AWS access keys in `.env` or source code.

## 3. Security group

For the initial POC, allow SSH from your IP and HTTP for the application. Prefer HTTPS and restricted access before exposing the system to real users.

## 4. Deploy

Copy the Knowledge Fabric package to the instance and use the supplied deployment assets under:

```text
deploy/aws/
```

The deployment installs the Python runtime/application, configures the service, and starts the web application.

## 5. Configure Bedrock

Open:

```text
Admin → AI & Models
```

Select:

```text
Provider: Amazon Bedrock
```

Choose a model available to your account/region and use **Test Model**.

## 6. Run the first live test

Open:

```text
Evaluation → Live Test Lab
```

Start small:

- Repository: `psf/requests`
- 5 benchmark questions
- 1 Bedrock model

Do not run large benchmark matrices until you understand the token and inference cost.

## Cost safety

Enable AWS billing/free-tier alerts and monitor Bedrock usage. Free-tier/credit eligibility does not mean unlimited Bedrock inference.

## Production evolution

When the POC is validated, migrate:

- local files → S3
- local metadata → PostgreSQL/DynamoDB
- local vector index → managed search/vector backend
- synchronous ingestion → queue + workers
- simple admin key → OIDC/SSO + RBAC
