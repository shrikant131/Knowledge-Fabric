"""Connector factory.

Dispatches on connector_type so the registry/pipeline never needs an
if/elif chain of its own -- add a new source type by adding one entry here
and implementing the SourceConnector interface.
"""
from __future__ import annotations

from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.connectors.base import SourceConnector


def build_connector(cfg: PipelineConfig) -> SourceConnector:
    opts = cfg.connector_options or {}

    if cfg.connector_type == "file":
        from knowledge_fabric.connectors.file_connector import FileConnector
        return FileConnector(
            source_id=cfg.source_id,
            root_path=opts.get("root_path", "./sample_data"),
        )

    if cfg.connector_type == "github":
        from knowledge_fabric.connectors.github_connector import GitHubConnector
        return GitHubConnector(
            source_id=cfg.source_id,
            owner=opts["owner"],
            repo=opts["repo"],
            ref=opts.get("ref"),
            token_env_var=opts.get("token_env_var", "GITHUB_TOKEN"),
            max_file_bytes=int(opts.get("max_file_bytes", 1000000)),
            max_files=int(opts.get("max_files", 10000)),
        )

    if cfg.connector_type == "confluence":
        from knowledge_fabric.connectors.confluence_connector import ConfluenceConnector
        return ConfluenceConnector(
            source_id=cfg.source_id,
            base_url=opts["base_url"],
            space_key=opts["space_key"],
            auth_env_var=opts.get("auth_env_var", "CONFLUENCE_API_TOKEN"),
            user_email_env_var=opts.get("user_email_env_var", "CONFLUENCE_USER_EMAIL"),
            cursor_path=opts.get("cursor_path", f"{cfg.index_dir}/{cfg.source_id}_cursor.txt"),
        )

    if cfg.connector_type == "sharepoint":
        from knowledge_fabric.connectors.sharepoint_connector import SharePointConnector
        return SharePointConnector(
            source_id=cfg.source_id,
            site_id=opts["site_id"],
            drive_id=opts["drive_id"],
            auth_env_var=opts.get("auth_env_var", "SHAREPOINT_ACCESS_TOKEN"),
            delta_token_path=opts.get("delta_token_path", f"{cfg.index_dir}/{cfg.source_id}_delta.txt"),
        )

    raise ValueError(f"Unknown connector_type: {cfg.connector_type!r}")
