from egregora_v3.core.context import Context


def build_embeddings(ctx: Context, batch_size: int = 100):
    """
    Finds chunks without embeddings, generates embeddings for them,
    and upserts them into the vector store.
    """
    ctx.logger.info("Starting embedding build process...")

    chunks_to_embed = ctx.conn.execute("""
        SELECT c.chunk_id, c.text
        FROM rag_chunks c
        LEFT JOIN rag_vectors v ON c.chunk_id = v.chunk_id
        WHERE v.chunk_id IS NULL;
    """).fetchall()

    if not chunks_to_embed:
        ctx.logger.info("No new chunks to embed. Index is up to date.")
        return

    ctx.logger.info(f"Found {len(chunks_to_embed)} chunks to embed.")

    total_embedded = 0
    for i in range(0, len(chunks_to_embed), batch_size):
        batch = chunks_to_embed[i:i + batch_size]
        chunk_ids, texts = zip(*batch, strict=False)

        embeddings = ctx.embedding_client.embed(list(texts))
        vectors_to_upsert = list(zip(chunk_ids, embeddings, strict=False))

        ctx.vector_store.upsert(vectors_to_upsert)

        total_embedded += len(batch)
        ctx.logger.info(f"Embedded and upserted batch {i//batch_size + 1}, total embedded: {total_embedded}")

    ctx.logger.info(f"Embedding build process complete. Total chunks embedded: {total_embedded}")
