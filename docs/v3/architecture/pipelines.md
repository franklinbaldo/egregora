# Agent Pipelines

Pipelines in Egregora Pure are sequences of functional transformations.

## The `Write` Pipeline

1.  **Ingest:** Read raw data from `InputAdapter` (e.g., WhatsApp zip).
2.  **Normalize:** Convert raw data to `Entry` stream.
3.  **Window:** Group entries into coherent windows (Time/Count).
4.  **Enrich (Agent):** Extract metadata, generate slugs, describe media.
5.  **Write (Agent):** Generate blog post content from windows.
6.  **Publish:** Persist `Document` to `OutputSink` (e.g., MkDocs).

## The `Read` Pipeline

1.  **Scan:** Read existing `Document`s.
2.  **Rank (Agent):** Compare posts using ELO rating system.
3.  **Update:** Store new rankings.
