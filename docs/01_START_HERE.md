# Knowledge Fabric — Start Here

Knowledge Fabric is a local- and cloud-deployable agentic knowledge platform combining ingestion, hybrid RAG, agents, citations, evaluation, and optional LLM generation.

## Fastest local start

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

Open the browser Playground and choose Sample Knowledge, Upload Files, or GitHub.

Docker is optional for local development.

## Fastest AWS start

For the current POC, use a Free Tier/credit-eligible EC2 instance and the AWS deployment assets included with the product.

High-level flow:

1. Launch an eligible EC2 instance.
2. Attach an IAM role with the minimum Bedrock permissions.
3. Upload/deploy the Knowledge Fabric package.
4. Run the EC2 deployment script.
5. Open `/playground`.
6. Configure Bedrock in Admin → AI & Models.
7. Run Live Test Lab against a small public repository.

Do not put AWS access keys in the application. Prefer the EC2 instance role.

## Product surfaces

- `/quick-start` — zero-configuration onboarding
- `/playground` — normal knowledge experience
- `/evaluation/live-lab` — real repository/LLM testing
- `/evaluation/benchmark-studio` — multi-configuration evaluation
- `/admin` — control plane
