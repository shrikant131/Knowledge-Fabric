@echo off
cd /d %~dp0
python -m knowledge_fabric.cli ingest --config manifest.yaml
python admin\app.py
