# Local Python Installation

## Requirements

- Python 3.10+ recommended
- Git recommended
- No Docker required

## Install

```bash
python local_install.py
```

The installer creates an isolated virtual environment and installs the application.

## Start

```bash
kf start
```

or:

```bash
python -m knowledge_fabric.cli start
```

## Verify

```bash
kf status
```

Then open the browser URL printed by the command.

## First run

Use Quick Start:

1. Try Sample Knowledge.
2. Upload a few documents.
3. Import a public GitHub repository.
4. Ask a question in Playground.

## Optional LLM

Local mode should remain usable without an API key.

For cloud LLM use, configure Bedrock or an OpenAI-compatible provider from Admin → AI & Models.

## Data

Set `KF_DATA_DIR` to control where local state is stored:

```bash
export KF_DATA_DIR=/path/to/kf-data
```

Windows PowerShell:

```powershell
$env:KF_DATA_DIR="C:\kf-data"
```

Back up this directory if you need to preserve local indexes and configuration.
