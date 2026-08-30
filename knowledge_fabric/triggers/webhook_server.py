"""Webhook trigger adapter.

Standing in for the Webhook Receiver in the Reference Architecture (API
Gateway + Lambda in production). For push-capable sources like GitHub,
Slack, or Jira, the source calls this endpoint the moment something
changes, so ingestion reacts in seconds instead of waiting for the next
scheduler poll.

This uses Python's built-in http.server so the pilot has no extra
dependencies; a production deployment would replace this file with an API
Gateway + Lambda handler, but the contract is the same: verify the sender,
deduplicate by delivery id, then call pipeline.ingest().

Run:
    python -m knowledge_fabric.cli serve-webhook --config manifest.yaml --port 8787

Trigger it (simulating a GitHub push):
    curl -X POST http://localhost:8787/webhook/local_files \\
         -H "X-Webhook-Secret: dev-secret" \\
         -H "X-Delivery-Id: 1234"
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from http.server import HTTPServer

from knowledge_fabric.pipeline import KnowledgeFabricPipeline

logger = logging.getLogger("knowledge_fabric.webhook")

_seen_delivery_ids: set[str] = set()  # idempotency check, per Connector Framework doc


def make_handler(pipeline: KnowledgeFabricPipeline, shared_secret: str):
    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            expected_path = f"/webhook/{pipeline.cfg.source_id}"
            if self.path != expected_path:
                self._respond(404, {"error": f"unknown source, expected {expected_path}"})
                return

            secret = self.headers.get("X-Webhook-Secret")
            if secret != shared_secret:
                self._respond(401, {"error": "invalid or missing X-Webhook-Secret"})
                return

            delivery_id = self.headers.get("X-Delivery-Id", "")
            if delivery_id and delivery_id in _seen_delivery_ids:
                self._respond(200, {"status": "duplicate delivery, skipped", "delivery_id": delivery_id})
                return
            if delivery_id:
                _seen_delivery_ids.add(delivery_id)

            logger.info("Webhook received for source '%s' (delivery_id=%s) — running ingest",
                        pipeline.cfg.source_id, delivery_id or "n/a")
            try:
                result = pipeline.ingest()
                self._respond(200, {"status": "ingested", **result})
            except Exception as e:
                logger.exception("Webhook-triggered ingest failed")
                self._respond(500, {"error": str(e)})

        def _respond(self, code: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            # avoid self.address_string(): it does a reverse DNS lookup
            # (socket.getfqdn) that can hang badly on networks without
            # working reverse DNS -- use the raw client IP instead.
            logger.info("%s - %s", self.client_address[0], fmt % args)

    return WebhookHandler


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def serve(pipeline: KnowledgeFabricPipeline, port: int = 8787, shared_secret: str = "dev-secret") -> None:
    handler = make_handler(pipeline, shared_secret)
    server = _ThreadingHTTPServer(("0.0.0.0", port), handler)
    logger.info(
        "Webhook listener started on port %d for source '%s'. POST to /webhook/%s",
        port, pipeline.cfg.source_id, pipeline.cfg.source_id,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Webhook listener stopped.")
