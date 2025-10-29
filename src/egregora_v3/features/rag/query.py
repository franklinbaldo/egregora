
from egregora_v3.core.context import Context
from egregora_v3.core.types import QueryHit, RagChunk


def query_rag(ctx: Context, query_text: str, k: int = 8, mode: str = "ann") -> list[QueryHit]:
    """
    Performs a RAG query against the vector store.
    """
    ctx.logger.info(f"Performing RAG query for: '{query_text}'")

    query_embedding_result = ctx.embedding_client.embed([query_text], task_type="retrieval_query")

    if isinstance(query_embedding_result, list) and query_embedding_result:
        query_embedding = query_embedding_result[0]
    else:
        query_embedding = query_embedding_result

    hits = ctx.vector_store.query(query_embedding, k=k)

    if not hits:
        return []

    hit_ids = [h[0] for h in hits]
    similarity_map = {h[0]: h[1] for h in hits}

    placeholders = ', '.join('?' for _ in hit_ids)

    chunk_results = ctx.conn.execute(
        f"SELECT * FROM rag_chunks WHERE chunk_id IN ({placeholders})",
        hit_ids
    ).fetchall()

    query_hits = []
    if chunk_results:
        column_names = [desc[0] for desc in ctx.conn.description]
        for row in chunk_results:
            row_dict = dict(zip(column_names, row, strict=False))
            chunk = RagChunk(**row_dict)
            similarity = similarity_map.get(chunk.chunk_id)
            query_hits.append(QueryHit(chunk=chunk, similarity=similarity))

    # Sort by distance in ascending order (smaller is better)
    query_hits.sort(key=lambda x: x.similarity)

    return query_hits
