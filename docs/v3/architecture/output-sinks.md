# Output Sinks

An `OutputSink` is the destination for processed `Document`s.

## MkDocs Adapter

The primary sink for Egregora is the **MkDocs Adapter**. It writes documents as Markdown files in a directory structure compatible with `mkdocs-material`.

*   **Structure:**
    *   `docs/posts/YYYY/MM/slug.md`
    *   `docs/posts/media/`
    *   `docs/posts/profiles/`

## Parquet Adapter

For analytics and data interchange, the **Parquet Adapter** writes documents to partitioned Parquet files.
