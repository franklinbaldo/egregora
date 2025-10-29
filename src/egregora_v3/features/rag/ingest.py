import hashlib
from collections.abc import Iterator
from pathlib import Path

from egregora_v3.adapters.privacy.anonymize import anonymize_mentions
from egregora_v3.core.context import Context
from egregora_v3.core.types import RagChunk


def chunk_document(doc_content: str, chunk_size: int = 1024) -> Iterator[str]:
    """
    A simple chunking strategy that splits text by a fixed size.
    """
    for i in range(0, len(doc_content), chunk_size):
        yield doc_content[i:i + chunk_size]

def ingest_source(ctx: Context, source_path: Path):
    """
    Ingests a source document, chunks it, anonymizes it, and saves it to the database.
    """
    ctx.logger.info(f"Ingesting source file: {source_path}")

    doc_content = source_path.read_text()
    anonymized_content = anonymize_mentions(doc_content)

    chunks_to_insert = []
    for chunk_text in chunk_document(anonymized_content):
        chunk_id = hashlib.sha256(chunk_text.encode()).hexdigest()
        slug = source_path.stem

        chunk = RagChunk(
            chunk_id=chunk_id,
            slug=slug,
            text=chunk_text,
            source=str(source_path)
        )
        chunks_to_insert.append(chunk.model_dump())

    if chunks_to_insert:
        ctx.conn.execute("CREATE TEMP TABLE temp_chunks (chunk_id TEXT, slug TEXT, text TEXT, source TEXT, created_at TIMESTAMP);")

        data_to_insert = [
            (c['chunk_id'], c['slug'], c['text'], c['source'], c['created_at'].isoformat())
            for c in chunks_to_insert
        ]

        ctx.conn.executemany("INSERT INTO temp_chunks VALUES (?, ?, ?, ?, ?)", data_to_insert)

        ctx.conn.execute("""
            INSERT INTO rag_chunks (chunk_id, slug, text, source, created_at)
            SELECT chunk_id, slug, text, source, created_at FROM temp_chunks
            ON CONFLICT (chunk_id) DO NOTHING;
        """)

        ctx.conn.execute("DROP TABLE temp_chunks;")
        ctx.conn.commit()

    ctx.logger.info(f"Successfully ingested {len(chunks_to_insert)} chunks from {source_path}")
