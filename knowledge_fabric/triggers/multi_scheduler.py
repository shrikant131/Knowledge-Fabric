"""Runs a scheduler loop per registered source, in parallel threads.

This is what makes the registry "live": once a source is registered via
the admin page or CLI, this orchestrator picks it up and starts polling it
independently, on that source's own configured interval, without the other
sources' loops blocking on it.
"""
from __future__ import annotations

import logging
import threading

from knowledge_fabric.registry import ConnectorRegistry

logger = logging.getLogger("knowledge_fabric.multi_scheduler")


class MultiSourceScheduler:
    def __init__(self, registry: ConnectorRegistry):
        self.registry = registry
        self._threads: dict[str, threading.Thread] = {}
        self._stop_flags: dict[str, threading.Event] = {}

    def start_all(self) -> None:
        for cfg in self.registry.list_sources():
            self.start_source(cfg.source_id)

    def start_source(self, source_id: str) -> None:
        if source_id in self._threads and self._threads[source_id].is_alive():
            return  # already running
        stop_event = threading.Event()
        self._stop_flags[source_id] = stop_event
        thread = threading.Thread(
            target=self._run_loop, args=(source_id, stop_event), daemon=True,
            name=f"watch-{source_id}",
        )
        self._threads[source_id] = thread
        thread.start()
        self.registry.set_watching(source_id, True)
        logger.info("Started watch loop for source '%s'", source_id)

    def stop_source(self, source_id: str) -> None:
        event = self._stop_flags.get(source_id)
        if event:
            event.set()
        self.registry.set_watching(source_id, False)
        logger.info("Stopped watch loop for source '%s'", source_id)

    def is_running(self, source_id: str) -> bool:
        thread = self._threads.get(source_id)
        return thread is not None and thread.is_alive()

    def _run_loop(self, source_id: str, stop_event: threading.Event) -> None:
        cfg = self.registry.get_source(source_id)
        if cfg is None:
            logger.error("Source '%s' not found in registry; loop exiting", source_id)
            return
        pipeline = self.registry.build_pipeline(source_id)
        interval = max(5, cfg.poll_interval_seconds)

        while not stop_event.is_set():
            try:
                result = pipeline.ingest()
                self.registry.record_run(source_id, result)
                if result["chunks_ingested"] > 0:
                    logger.info("source=%s changed=%d chunks_ingested=%d",
                                source_id, result["items_changed"], result["chunks_ingested"])
            except Exception as e:
                logger.exception("Ingestion cycle failed for source '%s'", source_id)
                self.registry.record_run(source_id, None, error=str(e))

            stop_event.wait(interval)

        self.registry.set_watching(source_id, False)
