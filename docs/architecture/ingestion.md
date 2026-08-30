# Ingestion architecture

The ingestion path is:

`Connector → RawItem → Parse → ParsedDocument → Chunk → Embed → Store`

Content hashes provide stable change detection. An unchanged item should not be reprocessed unnecessarily.

Connectors should remain stateless where possible; persistent source status belongs in the registry/control plane.
