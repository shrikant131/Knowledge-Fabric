"""Stable runtime paths independent of the process working directory."""
from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def root_path(value: str | Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p

def data_dir() -> Path:
    return root_path(os.getenv("KF_DATA_DIR", "data"))

def manifests_dir() -> Path:
    return root_path(os.getenv("KF_CONNECTORS_DIR", "connectors_registry"))

def registry_status_path() -> Path:
    return data_dir() / "registry_status.json"

def admin_config_path() -> Path:
    return data_dir() / "admin_config.json"

def admin_audit_path() -> Path:
    return data_dir() / "admin_audit.jsonl"
