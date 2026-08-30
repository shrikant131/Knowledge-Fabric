"""Live end-to-end LLM smoke test against a public GitHub repository.

Examples:
  python tools_live_llm_test.py --repo psf/requests --provider openai
  python tools_live_llm_test.py --repo pallets/flask --provider bedrock

The test intentionally refuses to fabricate a live result: if the provider
credentials/network are unavailable it reports SKIPPED with the exact reason.
"""
from __future__ import annotations
import argparse, os, sys, tempfile, json
from pathlib import Path

from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.pipeline import KnowledgeFabricPipeline


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo', default='psf/requests')
    ap.add_argument('--ref')
    ap.add_argument('--provider', choices=['openai','bedrock'], required=True)
    ap.add_argument('--model')
    args=ap.parse_args()
    owner,repo=args.repo.split('/',1)
    index=tempfile.mkdtemp(prefix='kf-live-')
    cfg=PipelineConfig(
        source_id=f'github:{owner}/{repo}', connector_type='github',
        connector_options={'owner':owner,'repo':repo,'ref':args.ref},
        index_dir=index, llm_enabled=True, llm_provider=args.provider,
        generator=args.provider,
    )
    if args.model:
        if args.provider=='openai': cfg.openai_chat_model=args.model
        else: cfg.bedrock_chat_model=args.model
    print(f'LIVE TEST: {args.repo} / provider={args.provider}')
    try:
        p=KnowledgeFabricPipeline(cfg)
        result=p.ingest()
        print('INGEST:', json.dumps(result))
        questions=[
            'What is the main purpose of this repository?',
            'Where is the primary request/session implementation defined?',
            'What is one important design or error-handling behavior documented in the repository?',
        ]
        for q in questions:
            r=p.query(q)
            print('\nQUESTION:',q)
            print('ANSWER:',r['answer'])
            print('CONFIDENCE:',r['confidence'])
            print('SOURCES:', [x['citation'] for x in r['retrieved'][:5]])
            print('TRACE:', r['trace'])
        print('\nLIVE TEST: PASSED')
    except Exception as exc:
        msg=str(exc)
        if 'OPENAI_API_KEY' in msg or 'Unable to locate credentials' in msg or 'Could not connect' in msg or 'Name or service not known' in msg:
            print(f'LIVE TEST: SKIPPED - provider/network unavailable: {msg}')
            return 2
        raise

if __name__=='__main__': sys.exit(main())
