"""Bounded background jobs with stable runtime storage."""
from __future__ import annotations
import json, os, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from knowledge_fabric.runtime_paths import data_dir

class JobStore:
    def __init__(self,path=None):
        self.path=Path(path) if path else data_dir()/"jobs.json"
        self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=Lock()
    def _read(self):
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception: return {}
    def _write(self,data):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2,default=str),encoding='utf-8'); tmp.replace(self.path)
    def put(self,job):
        with self.lock: d=self._read(); d[job['job_id']]=job; self._write(d)
    def get(self,jid): return self._read().get(jid)
    def list(self,limit=100): return sorted(self._read().values(),key=lambda x:x.get('created_at',''),reverse=True)[:limit]

class JobManager:
    def __init__(self,workers=2,store=None): self.store=store or JobStore(); self.pool=ThreadPoolExecutor(max_workers=max(1,int(workers)))
    def submit(self,kind,fn,*args,**kwargs):
        jid=f'job-{uuid.uuid4().hex[:12]}'; job={'job_id':jid,'kind':kind,'status':'queued','created_at':datetime.now(timezone.utc).isoformat(),'started_at':None,'finished_at':None,'result':None,'error':None}; self.store.put(job); self.pool.submit(self._run,jid,fn,args,kwargs); return job
    def _run(self,jid,fn,args,kwargs):
        job=self.store.get(jid) or {}; job.update(status='running',started_at=datetime.now(timezone.utc).isoformat()); self.store.put(job)
        try: job.update(status='completed',result=fn(*args,**kwargs))
        except Exception as exc: job.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        job['finished_at']=datetime.now(timezone.utc).isoformat(); self.store.put(job)

def build_manager(): return JobManager(int(os.getenv('KF_JOB_WORKERS','2')))
