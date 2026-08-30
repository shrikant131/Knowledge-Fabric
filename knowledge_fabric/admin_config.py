from __future__ import annotations
import json, threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

class AdminConfigStore:
    """Persistent control-plane configuration with optimistic versioning and audit history."""
    def __init__(self, path='./data/admin_config.json', audit_path='./data/admin_audit.jsonl'):
        self.path=Path(path); self.audit_path=Path(audit_path)
        self.path.parent.mkdir(parents=True, exist_ok=True); self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock=threading.Lock(); self._data=self._load()
    def _load(self):
        if not self.path.exists(): return {'version':0,'updated_at':None,'settings':{}}
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {'version':0,'updated_at':None,'settings':{}}
    def snapshot(self):
        with self._lock: return deepcopy(self._data)
    def update(self, changes, actor='admin', reason='control-plane update', expected_version=None):
        with self._lock:
            current=int(self._data.get('version',0))
            if expected_version is not None and int(expected_version)!=current:
                raise ValueError(f'configuration version conflict: expected {expected_version}, current {current}')
            before=deepcopy(self._data.get('settings',{})); settings=deepcopy(before); settings.update(changes)
            changed={k:{'old':before.get(k),'new':settings.get(k)} for k in settings if before.get(k)!=settings.get(k)}
            self._data={'version':current+1,'updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'settings':settings}
            self.path.write_text(json.dumps(self._data,indent=2))
            if changed:
                event={'timestamp':self._data['updated_at'],'actor':actor,'reason':reason,'version':self._data['version'],'changes':changed}
                with self.audit_path.open('a') as f: f.write(json.dumps(event)+'\n')
            return deepcopy(self._data), changed
    def audit(self, limit=100):
        if not self.audit_path.exists(): return []
        lines=self.audit_path.read_text().splitlines()[-limit:]
        out=[]
        for line in reversed(lines):
            try: out.append(json.loads(line))
            except Exception: pass
        return out
