"""CLI entry point for the RAG subsystem."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .server import run_server

console = Console()
app = typer.Typer(help="Manage the RAG context server.")


@app.command("serve")
def rag_serve(
    parquet_path: Path = typer.Argument(
        ..., help="Path to the embeddings Parquet file."
    ),
) -> None:
    """
    Starts the FastMCP server for RAG context.
    """
    run_server(parquet_path)


if __name__ == "__main__":
    app()
