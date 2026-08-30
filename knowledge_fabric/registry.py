"""Connector registry -- the backing model for the central admin page.

Every registered source is one manifest YAML file in a manifests
directory. The registry loads them all, can build a pipeline for any one
of them on demand, and persists a small status record per source (last
run time, result, error) so the admin UI has something to show without
needing every pipeline live in memory at once.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.pipeline import KnowledgeFabricPipeline


@dataclass
class SourceStatus:
    source_id: str
    last_run_at: Optional[str] = None
    last_result: Optional[dict] = None
    last_error: Optional[str] = None
    total_runs: int = 0
    watching: bool = False


class ConnectorRegistry:
    def __init__(self, manifests_dir: str = "./connectors_registry", status_path: str = "./data/registry_status.json"):
        self.manifests_dir = Path(manifests_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.status_path = Path(status_path)
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._status: dict[str, SourceStatus] = self._load_status()

    # ---- manifest management --------------------------------------------
    def list_sources(self) -> list[PipelineConfig]:
        configs = []
        for path in sorted(self.manifests_dir.glob("*.yaml")):
            try:
                configs.append(PipelineConfig.from_yaml(str(path)))
            except Exception:
                continue
        return configs

    def get_source(self, source_id: str) -> Optional[PipelineConfig]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", source_id or ""):
            return None
        path = self.manifests_dir / f"{source_id}.yaml"
        if not path.exists():
            return None
        return PipelineConfig.from_yaml(str(path))

    def register(self, cfg: PipelineConfig) -> None:
        """Add or update a source manifest after validating its identifier."""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", cfg.source_id):
            raise ValueError("source_id must be 1-128 characters: letters, numbers, _, ., -")
        path = self.manifests_dir / f"{cfg.source_id}.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(cfg.to_yaml_dict(), f, sort_keys=False)
        with self._lock:
            if cfg.source_id not in self._status:
                self._status[cfg.source_id] = SourceStatus(source_id=cfg.source_id)
                self._save_status()

    def unregister(self, source_id: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", source_id or ""):
            return
        path = self.manifests_dir / f"{source_id}.yaml"
        if path.exists():
            path.unlink()
        with self._lock:
            self._status.pop(source_id, None)
            self._save_status()

    def build_pipeline(self, source_id: str) -> KnowledgeFabricPipeline:
        cfg = self.get_source(source_id)
        if cfg is None:
            raise KeyError(f"No registered source: {source_id}")
        return KnowledgeFabricPipeline(cfg)

    # ---- status tracking -----------------------------------------------
    def record_run(self, source_id: str, result: Optional[dict], error: Optional[str] = None) -> None:
        with self._lock:
            status = self._status.setdefault(source_id, SourceStatus(source_id=source_id))
            status.last_run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            status.last_result = result
            status.last_error = error
            status.total_runs += 1
            self._save_status()

    def set_watching(self, source_id: str, watching: bool) -> None:
        with self._lock:
            status = self._status.setdefault(source_id, SourceStatus(source_id=source_id))
            status.watching = watching
            self._save_status()

    def get_status(self, source_id: str) -> SourceStatus:
        with self._lock:
            return self._status.get(source_id, SourceStatus(source_id=source_id))

    def all_status(self) -> dict[str, SourceStatus]:
        with self._lock:
            return dict(self._status)

    def _load_status(self) -> dict[str, SourceStatus]:
        if not self.status_path.exists():
            return {}
        try:
            with open(self.status_path) as f:
                raw = json.load(f)
            return {sid: SourceStatus(**data) for sid, data in raw.items()}
        except Exception:
            return {}

    def _save_status(self) -> None:
        with open(self.status_path, "w") as f:
            json.dump({sid: asdict(s) for sid, s in self._status.items()}, f, indent=2)
