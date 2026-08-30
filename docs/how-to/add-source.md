# Add a knowledge source

## File source

1. Select **Add source**.
2. Choose `file`.
3. Set a unique source ID.
4. Set the root directory.
5. Keep LLM OFF initially.
6. Register the source.
7. Click **Sync**.

The connector supports common source files including Markdown, text, Python, Java and PDF.

## Confluence

Configure the base URL, space key and environment-variable names for the authentication token and user email. Keep credentials outside manifests.

## SharePoint

Configure site ID, drive ID and the environment variable containing the access token. Use Graph delta polling for incremental synchronization.

## Adding another connector

Implement the connector contract used by the existing connector registry. Return stable `RawItem` identifiers and content hashes. Add tests for initial sync, unchanged items, changed items and deletions before registering the connector.
