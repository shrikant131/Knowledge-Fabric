"""Scheduler trigger adapter.

This is the piece that makes ingestion "agentic" rather than manual: once a
source is registered (via its manifest), this loop runs indefinitely,
re-invoking the pipeline's ingest() on a fixed cadence. Because ingest()
already does delta detection internally (via content-hash / detect_delta),
each poll is cheap when nothing changed and only does work when something
did -- this is the same idempotent-at-least-once model described in the
Connector Framework design doc, just running as a loop instead of once.

For sources with native change notifications (GitHub, Slack, Jira), a
webhook adapter (see webhook_server.py) reacts immediately instead of
waiting for the next poll -- this scheduler is the fallback path used for
sources without webhooks (Confluence, SharePoint, generic file shares),
matching the Reference Architecture's trigger mapping.
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from knowledge_fabric.pipeline import KnowledgeFabricPipeline

logger = logging.getLogger("knowledge_fabric.scheduler")


class SchedulerTrigger:
    def __init__(self, pipeline: KnowledgeFabricPipeline, interval_seconds: int = 30):
        self.pipeline = pipeline
        self.interval_seconds = interval_seconds
        self._stop = False

    def _handle_signal(self, signum, frame):
        logger.info("Received stop signal, finishing current cycle then exiting.")
        self._stop = True

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        source_id = self.pipeline.cfg.source_id
        logger.info(
            "Scheduler started for source '%s' (poll every %ss). Ctrl+C to stop.",
            source_id, self.interval_seconds,
        )
        while not self._stop:
            cycle_start = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                result = self.pipeline.ingest()
                if result["chunks_ingested"] > 0:
                    logger.info(
                        "[%s] source=%s scanned=%d changed=%d chunks_ingested=%d",
                        cycle_start, source_id, result["items_scanned"],
                        result["items_changed"], result["chunks_ingested"],
                    )
                else:
                    logger.info(
                        "[%s] source=%s scanned=%d — no changes, vector store already fresh",
                        cycle_start, source_id, result["items_scanned"],
                    )
            except Exception:
                logger.exception("Ingestion cycle failed for source '%s'", source_id)
                # A real deployment would route this to the retry/DLQ path
                # from the Connector Framework doc rather than crash the loop.

            for _ in range(self.interval_seconds):
                if self._stop:
                    break
                time.sleep(1)

        logger.info("Scheduler stopped for source '%s'.", source_id)
