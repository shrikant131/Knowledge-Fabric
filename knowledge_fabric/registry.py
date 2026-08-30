"""Connector registry -- the backing model for the central admin page."""
from __future__ import annotations
import json, re, threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import yaml
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.pipeline import KnowledgeFabricPipeline
from knowledge_fabric.runtime_paths import manifests_dir, registry_status_path

@dataclass
class SourceStatus:
    source_id: str
    last_run_at: Optional[str] = None
    last_result: Optional[dict] = None
    last_error: Optional[str] = None
    total_runs: int = 0
    watching: bool = False

class ConnectorRegistry:
    def __init__(self, manifests_dir: str | None = None, status_path: str | None = None):
        self.manifests_dir = Path(manifests_dir) if manifests_dir else manifests_dir_path()
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.status_path = Path(status_path) if status_path else registry_status_path()
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock=threading.Lock(); self._status=self._load_status()
    def list_sources(self):
        out=[]
        for path in sorted(self.manifests_dir.glob("*.yaml")):
            try: out.append(PipelineConfig.from_yaml(str(path)))
            except Exception: continue
        return out
    def get_source(self, source_id):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", source_id or ""): return None
        path=self.manifests_dir/f"{source_id}.yaml"
        if not path.exists(): return None
        return PipelineConfig.from_yaml(str(path))
    def register(self,cfg):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",cfg.source_id): raise ValueError("source_id must be 1-128 characters: letters, numbers, _, ., -")
        path=self.manifests_dir/f"{cfg.source_id}.yaml"
        path.write_text(yaml.safe_dump(cfg.to_yaml_dict(),sort_keys=False),encoding="utf-8")
        with self._lock:
            if cfg.source_id not in self._status:
                self._status[cfg.source_id]=SourceStatus(source_id=cfg.source_id); self._save_status()
    def unregister(self,source_id):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",source_id or ""): return
        path=self.manifests_dir/f"{source_id}.yaml"
        if path.exists(): path.unlink()
        with self._lock: self._status.pop(source_id,None); self._save_status()
    def build_pipeline(self,source_id):
        cfg=self.get_source(source_id)
        if cfg is None: raise KeyError(f"No registered source: {source_id}")
        return KnowledgeFabricPipeline(cfg)
    def record_run(self,source_id,result,error=None):
        with self._lock:
            s=self._status.setdefault(source_id,SourceStatus(source_id=source_id)); s.last_run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"); s.last_result=result; s.last_error=error; s.total_runs+=1; self._save_status()
    def set_watching(self,source_id,watching):
        with self._lock: self._status.setdefault(source_id,SourceStatus(source_id=source_id)).watching=watching; self._save_status()
    def get_status(self,source_id):
        with self._lock: return self._status.get(source_id,SourceStatus(source_id=source_id))
    def all_status(self):
        with self._lock: return dict(self._status)
    def _load_status(self):
        try: raw=json.loads(self.status_path.read_text()); return {sid:SourceStatus(**data) for sid,data in raw.items()}
        except Exception: return {}
    def _save_status(self):
        tmp=self.status_path.with_suffix(self.status_path.suffix+'.tmp')
        tmp.write_text(json.dumps({sid:asdict(s) for sid,s in self._status.items()},indent=2),encoding="utf-8"); tmp.replace(self.status_path)

def manifests_dir_path():
    return manifests_dir()
