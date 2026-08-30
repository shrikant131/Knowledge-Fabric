"""Benchmark Studio: compare repositories, providers and RAG configurations."""
from __future__ import annotations
import json, time, uuid, statistics
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict
from .live_benchmark import run_benchmark, DEFAULT_CASES

class BenchmarkStudioStore:
    def __init__(self, path='./data/benchmark_studio.json'):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
    def list(self, limit=100):
        if not self.path.exists(): return []
        try: data=json.loads(self.path.read_text())
        except Exception: return []
        return data[-limit:][::-1]
    def append(self, record):
        data=self.list(10000)[::-1] if self.path.exists() else []
        data.append(record)
        self.path.write_text(json.dumps(data[-100:], indent=2))
        return record


def _score_run(run):
    m=run.get('metrics') or {}
    cases=m.get('cases',0) or 0
    successful=m.get('successful_cases',0) or 0
    citation=m.get('citation_coverage',0) or 0
    grounded=m.get('groundedness_proxy',0) or 0
    claim_cov=[]
    for c in run.get('cases',[]):
        cc=(c.get('confidence') or {}).get('claim_coverage')
        if cc is not None: claim_cov.append(float(cc))
    claim=statistics.mean(claim_cov) if claim_cov else grounded
    success=successful/cases if cases else 0
    # Transparent diagnostic score. It is not a factual correctness guarantee.
    quality=round(100*(0.35*citation + 0.40*claim + 0.25*success),1)
    return {
        'quality_score':quality,
        'citation_coverage':round(citation,3),
        'groundedness_proxy':round(grounded,3),
        'claim_coverage':round(claim,3),
        'success_rate':round(success,3),
        'avg_latency_ms':m.get('avg_latency_ms'),
        'p95_latency_ms':m.get('p95_latency_ms'),
        'input_tokens':m.get('input_tokens',0),
        'output_tokens':m.get('output_tokens',0),
    }


def run_studio(cfg, matrix, cases=None, index_root='./data/live_runs'):
    """Run a Cartesian benchmark matrix sequentially and persist one comparison record."""
    started=time.perf_counter()
    comparison_id='studio-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    runs=[]
    for item in matrix:
        repo=item.get('repo'); provider=item.get('provider','local'); model=item.get('model'); ref=item.get('ref')
        if not repo: continue
        run=run_benchmark(cfg, repo, provider=provider, model=model, ref=ref, cases=cases, index_root=index_root)
        run['studio_id']=comparison_id
        run['score']=_score_run(run)
        # Preserve experiment metadata for reproducibility.
        run['experiment']=item.get('experiment') or f'{provider}:{model or "default"}'
        runs.append(run)
    completed=[r for r in runs if r.get('status')=='completed']
    ranked=sorted(completed, key=lambda r:r.get('score',{}).get('quality_score',0), reverse=True)
    return {
        'studio_id':comparison_id,
        'started_at':datetime.now(timezone.utc).isoformat(),
        'duration_ms':int((time.perf_counter()-started)*1000),
        'matrix_size':len(matrix),
        'completed':len(completed),
        'blocked':sum(r.get('status')=='blocked' for r in runs),
        'failed':sum(r.get('status')=='failed' for r in runs),
        'runs':runs,
        'ranking':[{'rank':i+1,'run_id':r['run_id'],'repo':r['repo'],'provider':r['provider'],'model':r.get('model'),'experiment':r.get('experiment'),'score':r['score']} for i,r in enumerate(ranked)],
    }
