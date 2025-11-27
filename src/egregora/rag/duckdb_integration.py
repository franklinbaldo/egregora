"""DuckDB integration for LanceDB RAG backend.

This module provides integration between LanceDB vector search and DuckDB,
allowing you to:
- Query vector search results as DuckDB tables
- Join RAG results with existing DuckDB data
- Use SQL for analytics on vector search results
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import ibis

from egregora.rag import RAGQueryRequest, search

if TYPE_CHECKING:
    import ibis.expr.types as ir

logger = logging.getLogger(__name__)


def search_to_table(request: RAGQueryRequest) -> ir.Table:
    """Execute RAG search and return results as an Ibis table.

    This allows you to use DuckDB's SQL capabilities on vector search results,
    including joins with other tables, aggregations, and filtering.

    Args:
        request: RAG query request

    Returns:
        Ibis table with columns: chunk_id, text, score, document_id, document_type, etc.

    Example:
        >>> from egregora.rag import RAGQueryRequest
        >>> from egregora.rag.duckdb_integration import search_to_table
        >>> request = RAGQueryRequest(text="machine learning", top_k=10)
        >>> results_table = search_to_table(request)
        >>> # Now you can query with SQL
        >>> top_results = results_table.filter(results_table.score > 0.8)
        >>> print(top_results.execute())

    """
    response = search(request)

    # Convert RAGHit results to dictionary records
    records = []
    for hit in response.hits:
        record = {
            "document_id": hit.document_id,
            "chunk_id": hit.chunk_id,
            "text": hit.text,
            "score": hit.score,
        }
        # Add metadata fields as columns
        if hit.metadata:
            for key, value in hit.metadata.items():
                # Convert to string for safety (avoid type mismatches)
                record[key] = str(value) if value is not None else None

        records.append(record)

    # Create Ibis table from records
    if not records:
        # Return empty table with expected schema
        import pandas as pd

        empty_df = pd.DataFrame(columns=["chunk_id", "text", "score", "document_id", "document_type", "slug"])
        return ibis.memtable(empty_df)

    # Create table from records
    import pandas as pd

    df = pd.DataFrame(records)
    return ibis.memtable(df)


def join_with_messages(
    rag_results: ir.Table,
    messages_table: ir.Table,
    *,
    on_column: str = "document_id",
) -> ir.Table:
    """Join RAG search results with messages table.

    This is useful for enriching vector search results with full message data.

    Args:
        rag_results: Results from search_to_table()
        messages_table: Ibis table with message data
        on_column: Column to join on (default: "document_id")

    Returns:
        Joined table with both RAG and message columns

    Example:
        >>> rag_results = search_to_table(RAGQueryRequest(text="important topic"))
        >>> joined = join_with_messages(rag_results, messages_table)
        >>> # Now you have both similarity scores and full message content
        >>> print(joined.select("text", "score", "author_uuid", "ts").execute())

    """
    return rag_results.inner_join(messages_table, rag_results[on_column] == messages_table[on_column])


def create_rag_analytics_view(storage_manager, rag_query: str, top_k: int = 100) -> ir.Table:
    """Create a DuckDB view combining RAG results with analytics.

    This creates a materialized view that you can query with SQL, joining
    vector search results with your existing DuckDB tables.

    Args:
        storage_manager: DuckDB storage manager
        rag_query: Query text for RAG search
        top_k: Number of results to include

    Returns:
        Ibis table representing the analytics view

    Example:
        >>> from egregora.database.duckdb_manager import DuckDBStorageManager
        >>> storage = DuckDBStorageManager()
        >>> view = create_rag_analytics_view(
        ...     storage,
        ...     rag_query="machine learning trends",
        ...     top_k=50
        ... )
        >>> # Query the view with SQL
        >>> high_confidence = view.filter(view.score > 0.85)
        >>> print(high_confidence.count().execute())

    """
    # Execute RAG search
    request = RAGQueryRequest(text=rag_query, top_k=top_k)
    rag_table = search_to_table(request)

    # Register as a DuckDB table for querying
    with storage_manager.connection() as conn:
        # Convert to pandas for DuckDB registration
        df = rag_table.execute()
        conn.register("rag_search_results", df)

        # Create view combining RAG results with analytics
        view_sql = """
        SELECT
            r.*,
            COUNT(*) OVER (PARTITION BY r.document_type) as results_by_type,
            AVG(r.score) OVER (PARTITION BY r.document_type) as avg_score_by_type,
            ROW_NUMBER() OVER (ORDER BY r.score DESC) as rank
        FROM rag_search_results r
        """
        return conn.execute(view_sql).fetch_arrow_table()


def search_with_filters(
    query: str,
    *,
    min_score: float = 0.7,
    document_types: list[str] | None = None,
    top_k: int = 10,
) -> ir.Table:
    """Execute RAG search with SQL-based filtering.

    This combines vector search with SQL filtering for more precise results.

    Args:
        query: Search query text
        min_score: Minimum similarity score (default: 0.7)
        document_types: Filter by document types (e.g., ["POST", "NOTE"])
        top_k: Number of results to return

    Returns:
        Filtered Ibis table with search results

    Example:
        >>> results = search_with_filters(
        ...     "python programming",
        ...     min_score=0.8,
        ...     document_types=["POST"],
        ...     top_k=5
        ... )
        >>> for row in results.execute().to_pylist():
        ...     print(f"{row['text'][:50]}... (score: {row['score']:.2f})")

    """
    # Execute RAG search with higher top_k for pre-filtering
    request = RAGQueryRequest(text=query, top_k=top_k * 2)
    results = search_to_table(request)

    # Apply SQL filters
    filtered = results.filter(results.score >= min_score)

    if document_types:
        filtered = filtered.filter(filtered.document_type.isin(document_types))

    # Limit to requested top_k
    return filtered.order_by(filtered.score.desc()).limit(top_k)
