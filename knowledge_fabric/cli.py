"""Command-line interface for Knowledge Fabric."""
from __future__ import annotations
import argparse,json,logging,sys
from pathlib import Path
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.pipeline import KnowledgeFabricPipeline
from knowledge_fabric.runtime_paths import PROJECT_ROOT, root_path

def main():
    parent=argparse.ArgumentParser(add_help=False); parent.add_argument('--config',default='manifest.yaml',help='Path to manifest YAML')
    parser=argparse.ArgumentParser(prog='knowledge_fabric',parents=[parent]); sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init',parents=[parent],help='Create a zero-config local manifest'); sub.add_parser('start',help='Start browser control plane'); sub.add_parser('status',parents=[parent]); sub.add_parser('ingest',parents=[parent])
    qp=sub.add_parser('query',parents=[parent]); qp.add_argument('question')
    wp=sub.add_parser('watch',parents=[parent]); wp.add_argument('--interval',type=int,default=30)
    wh=sub.add_parser('serve-webhook',parents=[parent]); wh.add_argument('--port',type=int,default=8787); wh.add_argument('--secret',default='dev-secret')
    ep=sub.add_parser('evaluate',parents=[parent]); ep.add_argument('--golden',default='golden_dataset/sample_data.yaml'); ep.add_argument('--precision-threshold',type=float,default=.3); ep.add_argument('--recall-threshold',type=float,default=.5); ep.add_argument('--groundedness-threshold',type=float,default=.3)
    lp=sub.add_parser('live-test',parents=[parent]); lp.add_argument('--repo',default='psf/requests'); lp.add_argument('--provider',choices=['local','openai','bedrock'],default='local'); lp.add_argument('--model',default=None); lp.add_argument('--ref',default=None)
    fp=sub.add_parser('fairness',parents=[parent]); fp.add_argument('--threshold',type=float,default=1.0)
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO,format='%(levelname)s %(name)s: %(message)s')
    if args.command=='init':
        path=root_path(args.config)
        if not path.exists():
            import yaml
            cfg=PipelineConfig(source_id='local_files',display_name='Pilot Sample Data',connector_type='file',connector_options={'root_path':'./sample_data'})
            path.parent.mkdir(parents=True,exist_ok=True); path.write_text(yaml.safe_dump(cfg.to_yaml_dict(),sort_keys=False),encoding='utf-8'); print(f'Created {path}. Start with: kf start')
        else: print(f'{path} already exists. Start with: kf start')
        return
    if args.command=='start':
        import subprocess
        subprocess.run([sys.executable,str(PROJECT_ROOT/'admin'/'app.py')],cwd=str(PROJECT_ROOT),check=True); return
    config_path=root_path(args.config)
    try: cfg=PipelineConfig.from_yaml(str(config_path))
    except FileNotFoundError: print(f'Config file not found: {config_path}. Using defaults.',file=sys.stderr); cfg=PipelineConfig()
    pipeline=KnowledgeFabricPipeline(cfg)
    if args.command=='status': print(json.dumps({'source_id':cfg.source_id,'connector':cfg.connector_type,'llm_enabled':cfg.effective_llm_enabled(),'provider':cfg.llm_provider,'indexed_chunks':len(pipeline.store.chunks),'top_k':cfg.top_k},indent=2))
    elif args.command=='ingest': print(json.dumps(pipeline.ingest(),indent=2))
    elif args.command=='query':
        r=pipeline.query(args.question); print(f"\nIntent: {r['intent']}\n\nRetrieved ({len(r['retrieved'])} chunks):")
        for x in r['retrieved']: print(f"  [{x['score']:.3f}] {x['citation']}\n      {x['preview']}")
        print(f"\nAnswer:\n{r['answer']}\n")
    elif args.command=='watch':
        from knowledge_fabric.triggers.scheduler import SchedulerTrigger; SchedulerTrigger(pipeline,interval_seconds=args.interval).run_forever()
    elif args.command=='serve-webhook':
        from knowledge_fabric.triggers.webhook_server import serve; serve(pipeline,port=args.port,shared_secret=args.secret)
    elif args.command=='evaluate':
        from knowledge_fabric.evaluation.golden_dataset import load_golden_set,run_golden_set
        report=run_golden_set(pipeline,load_golden_set(str(root_path(args.golden))),precision_threshold=args.precision_threshold,recall_threshold=args.recall_threshold,groundedness_threshold=args.groundedness_threshold)
        for r in report.results: print(f"[{'PASS' if r.passed else 'FAIL'}] {r.case.id}: precision={r.precision_at_k:.2f} recall={r.recall:.2f} groundedness={r.groundedness_score:.2f} ({r.verdict})")
        print(f'\nMean precision={report.mean_precision:.2f} recall={report.mean_recall:.2f} groundedness={report.mean_groundedness:.2f}\nRegression gate: {"PASSED" if report.passed else "FAILED"}'); sys.exit(0 if report.passed else 1)
    elif args.command=='live-test':
        from knowledge_fabric.evaluation.live_benchmark import run_benchmark
        report=run_benchmark(cfg,args.repo,provider=args.provider,model=args.model,ref=args.ref); print(json.dumps(report,indent=2)); sys.exit(0 if report.get('status')=='completed' else 1)
    elif args.command=='fairness':
        from knowledge_fabric.evaluation.fairness import source_diversity_report
        report=source_diversity_report(pipeline.query_log.read_all(),pipeline.store,deviation_threshold=args.threshold); print(f'Analyzed {report.total_queries} logged queries against the current index.\n'); [print(f'  {f.item_id}: index_share={f.index_share:.2%} citation_share={f.citation_share:.2%}') for f in report.findings]
if __name__=='__main__': main()
