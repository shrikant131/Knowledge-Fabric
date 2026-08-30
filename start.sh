#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m knowledge_fabric.cli init --config manifest.yaml
python admin/app.py
