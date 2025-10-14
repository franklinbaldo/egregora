"""FastMCP server for the RAG context."""

from __future__ import annotations

import json
from pathlib import Path

import fastmcp as mcp
import polars as pl
from rich.console import Console

from ..embed.embed import get_embedding
from .duckdb_setup import create_ibis_search_function, setup_duckdb

console = Console()

def run_server(parquet_path: str | Path):
    """
    Runs an ephemeral FastMCP server for RAG context.

    Args:
        parquet_path: The path to the embeddings Parquet file.
    """
    console.print(f"🧠 Setting up DuckDB from: {parquet_path}")
    con = setup_duckdb(parquet_path)
    search_func = create_ibis_search_function(con)

    @mcp.tool
    def search_similar(query: str, k: int = 3) -> str:
        """
        Searches for similar embeddings in the DuckDB database.

        Args:
            query: The query string to search for.
            k: The number of similar items to return.

        Returns:
            A JSON string representing a list of dictionaries with the
            search results.
        """
        console.print(f"🔍 Searching for similar content to: '{query}' (k={k})")
        query_vector = get_embedding(query)
        results = search_func(query_vector, k)
        return json.dumps(results.to_dicts())

    server = mcp.server.server.FastMCP(tools=[search_similar])
    console.print("🚀 Starting FastMCP server on port 8000...")
    server.run(port=8000)
    console.print("🛑 Server shut down.")

if __name__ == "__main__":
    # Example usage: python -m egregora.rag_context.server <path_to_embeddings.parquet>
    import sys

    if len(sys.argv) > 1:
        run_server(sys.argv[1])
    else:
        console.print("❌ Please provide the path to the embeddings Parquet file.")
