"""Command-line interface for the Knowledge Fabric pilot.

Usage:
    python -m knowledge_fabric.cli ingest --config manifest.yaml
    python -m knowledge_fabric.cli query "How does the retry logic work?" --config manifest.yaml
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.pipeline import KnowledgeFabricPipeline


def main() -> None:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config", default="manifest.yaml", help="Path to manifest YAML")

    parser = argparse.ArgumentParser(prog="knowledge_fabric", parents=[parent])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", parents=[parent], help="Create a zero-config local manifest for the included sample knowledge")
    sub.add_parser("start", help="Start the browser control plane (zero-config)")
    sub.add_parser("status", parents=[parent], help="Show current source/index/LLM status")
    sub.add_parser("ingest", parents=[parent], help="Run ingestion once: scan the source and index new/changed content")

    query_parser = sub.add_parser("query", parents=[parent], help="Ask a question against the indexed content")
    query_parser.add_argument("question", help="The question to ask")

    watch_parser = sub.add_parser(
        "watch", parents=[parent], help="Run continuously: poll the source on an interval and auto-update the vector store"
    )
    watch_parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds")

    webhook_parser = sub.add_parser(
        "serve-webhook", parents=[parent], help="Run a webhook listener that triggers ingestion instantly on push"
    )
    webhook_parser.add_argument("--port", type=int, default=8787)
    webhook_parser.add_argument("--secret", default="dev-secret", help="Shared secret expected in X-Webhook-Secret")

    eval_parser = sub.add_parser(
        "evaluate", parents=[parent], help="Run the golden dataset regression suite (retrieval + groundedness gate)"
    )
    eval_parser.add_argument("--golden", default="golden_dataset/sample_data.yaml", help="Path to golden dataset YAML")
    eval_parser.add_argument("--precision-threshold", type=float, default=0.3)
    eval_parser.add_argument("--recall-threshold", type=float, default=0.5)
    eval_parser.add_argument("--groundedness-threshold", type=float, default=0.3)

    live_parser = sub.add_parser("live-test", parents=[parent], help="Run a real public GitHub -> RAG -> LLM benchmark")
    live_parser.add_argument("--repo", default="psf/requests")
    live_parser.add_argument("--provider", choices=["local","openai","bedrock"], default="local")
    live_parser.add_argument("--model", default=None)
    live_parser.add_argument("--ref", default=None)

    fairness_parser = sub.add_parser(
        "fairness", parents=[parent], help="Run the source-diversity fairness audit over the query log"
    )
    fairness_parser.add_argument("--threshold", type=float, default=1.0, help="Flag deviation beyond this fraction of expected share")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "init":
        path=Path(args.config)
        if not path.exists():
            cfg=PipelineConfig(source_id="local_files", display_name="Pilot Sample Data", connector_type="file", connector_options={"root_path":"./sample_data"})
            import yaml
            path.write_text(yaml.safe_dump(cfg.to_yaml_dict(), sort_keys=False))
            print(f"Created {path}. Start with: kf start")
        else:
            print(f"{path} already exists. Start with: kf start")
        return
    if args.command == "start":
        import subprocess
        subprocess.run([sys.executable, "admin/app.py"], check=True)
        return

    try:
        cfg = PipelineConfig.from_yaml(args.config)
    except FileNotFoundError:
        print(f"Config file not found: {args.config}. Using defaults.", file=sys.stderr)
        cfg = PipelineConfig()

    pipeline = KnowledgeFabricPipeline(cfg)

    if args.command == "status":
        print(json.dumps({"source_id":cfg.source_id,"connector":cfg.connector_type,"llm_enabled":cfg.effective_llm_enabled(),"provider":cfg.llm_provider,"indexed_chunks":len(pipeline.store.chunks),"top_k":cfg.top_k}, indent=2))
    elif args.command == "ingest":
        result = pipeline.ingest()
        print(json.dumps(result, indent=2))
    elif args.command == "query":
        result = pipeline.query(args.question)
        print(f"\nIntent: {result['intent']}")
        print(f"\nRetrieved ({len(result['retrieved'])} chunks):")
        for r in result["retrieved"]:
            print(f"  [{r['score']:.3f}] {r['citation']}")
            print(f"      {r['preview']}")
        print(f"\nAnswer:\n{result['answer']}\n")
    elif args.command == "watch":
        from knowledge_fabric.triggers.scheduler import SchedulerTrigger
        SchedulerTrigger(pipeline, interval_seconds=args.interval).run_forever()
    elif args.command == "serve-webhook":
        from knowledge_fabric.triggers.webhook_server import serve
        serve(pipeline, port=args.port, shared_secret=args.secret)
    elif args.command == "evaluate":
        from knowledge_fabric.evaluation.golden_dataset import load_golden_set, run_golden_set
        golden_cases = load_golden_set(args.golden)
        report = run_golden_set(
            pipeline, golden_cases,
            precision_threshold=args.precision_threshold,
            recall_threshold=args.recall_threshold,
            groundedness_threshold=args.groundedness_threshold,
        )
        for r in report.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.case.id}: precision={r.precision_at_k:.2f} recall={r.recall:.2f} "
                  f"groundedness={r.groundedness_score:.2f} ({r.verdict})")
            for reason in r.reasons:
                print(f"       - {reason}")
        print(f"\nMean precision={report.mean_precision:.2f} recall={report.mean_recall:.2f} "
              f"groundedness={report.mean_groundedness:.2f}")
        print(f"Regression gate: {'PASSED' if report.passed else 'FAILED'}")
        sys.exit(0 if report.passed else 1)
    elif args.command == "live-test":
        from knowledge_fabric.evaluation.live_benchmark import run_benchmark
        report = run_benchmark(cfg, args.repo, provider=args.provider, model=args.model, ref=args.ref)
        print(json.dumps(report, indent=2))
        if report.get("status") != "completed":
            sys.exit(1)
    elif args.command == "fairness":
        from knowledge_fabric.evaluation.fairness import source_diversity_report
        entries = pipeline.query_log.read_all()
        report = source_diversity_report(entries, pipeline.store, deviation_threshold=args.threshold)
        print(f"Analyzed {report.total_queries} logged queries against the current index.\n")
        if not report.findings:
            print("No source-diversity deviations beyond threshold.")
        for f in report.findings:
            direction = "OVER-cited" if f.deviation > 0 else "UNDER-cited"
            print(f"  {f.item_id}: index_share={f.index_share:.2%} citation_share={f.citation_share:.2%} "
                  f"({direction}, {f.deviation:+.0%} deviation)")


if __name__ == "__main__":
    main()
