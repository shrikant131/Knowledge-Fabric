# AWS App Runner

App Runner is the quickest cloud deployment path for a single Knowledge Fabric instance.

Build the repository using the included Dockerfile and deploy the image from ECR. Configure port `8080`, `KF_HOST=0.0.0.0`, `KF_PORT=8080`, and secrets through App Runner. For persistent production state, use external S3/Postgres/OpenSearch adapters rather than container-local JSON/index files.
