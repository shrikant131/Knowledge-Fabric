# Knowledge Fabric

An agentic knowledge platform with **RAG, tools, LLM integration, citations, Live Test Lab, Benchmark Studio, Playground, Admin Console, and CLI**.

This repository includes a security-hardened local/single-instance deployment profile and a cloud-ready architecture. Enterprise horizontal scaling still requires managed shared persistence and durable workers.

Knowledge Fabric is designed to run in two ways:

- **Local:** Python-installable, no Docker required.
- **Cloud:** container/VM deployable, including AWS + Bedrock.

## Quick Start — Local Python

### Windows PowerShell

```powershell
python local_install.py
.\.venv\Scripts\Activate.ps1
kf start
```

### Linux/macOS

```bash
python3 local_install.py
source .venv/bin/activate
kf start
```

Open the URL printed by the application.

Docker is optional.

## Product

| Surface | Purpose |
|---|---|
| `/quick-start` | Zero-configuration onboarding |
| `/playground` | Ask questions against knowledge |
| `/evaluation/live-lab` | Run live repository/LLM tests |
| `/evaluation/benchmark-studio` | Compare RAG/LLM configurations |
| `/admin` | Configure and operate the platform |

## CLI

```bash
kf status
kf query "How does authentication work?"
kf evaluate
```

## LLM

The product can operate without an LLM in local mode.

Optional providers include:

- Local
- OpenAI-compatible
- Amazon Bedrock

For AWS deployments, prefer an IAM role over static AWS credentials.

Copy the environment template:

```bash
cp .env.example .env
```

Never commit `.env`.

## AWS

See:

```text
docs/03_AWS_QUICK_DEPLOY.md
docs/04_CLOUD_ARCHITECTURE.md
```

The recommended first AWS POC is a small Free Tier/credit-eligible EC2 instance plus Bedrock. The production target uses managed persistence, workers, search/vector infrastructure, secrets, and observability.

## Documentation

Start with:

```text
docs/01_START_HERE.md
```

Then see the remaining files under `docs/`.

## Repository hygiene

Runtime data, indexes, logs, credentials, environments, and generated artifacts are intentionally excluded from Git via `.gitignore`.

## License

Add the license appropriate for your intended distribution before publishing publicly.
