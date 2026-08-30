#!/usr/bin/env bash
set -e
python3 local_install.py
. .venv/bin/activate
python run_local.py
