"""CLI entry point for the embed subsystem."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import typer
from rich.console import Console

from .embed import embed_dataframe, export_dataframe_to_parquet
from ..config import PipelineConfig

console = Console()
app = typer.Typer(help="Generate and manage embeddings for DataFrames.")


@app.command("run")
def embed_run(
    dataframe_path: Path = typer.Argument(..., help="Path to the input Parquet file."),
    output_path: Path = typer.Option(
        "embeddings.parquet", "--output", "-o", help="Path to save the output Parquet file."
    ),
    model: str = typer.Option(
        "models/embedding-001", "--model", help="The embedding model to use."
    ),
    batch_size: int = typer.Option(10, "--batch-size", help="Batch size for embedding requests."),
) -> None:
    """
    Loads a DataFrame, generates embeddings for the 'message' column,
    and saves the result to a new Parquet file.
    """
    console.print(f"📥 Loading DataFrame from: {dataframe_path}")
    if not dataframe_path.exists():
        console.print(f"❌ File not found: {dataframe_path}")
        raise typer.Exit(1)

    try:
        df = pl.read_parquet(dataframe_path)
    except Exception as e:
        console.print(f"❌ Error loading Parquet file: {e}")
        raise typer.Exit(1)

    console.print(f"🧠 Generating embeddings with model '{model}'...")

    # Here we would use the config, but for now we'll pass the CLI options directly
    embedded_df = embed_dataframe(
        df, text_column="message", model=model, batch_size=batch_size
    )

    console.print(f"💾 Saving DataFrame with embeddings to: {output_path}")
    export_dataframe_to_parquet(embedded_df, str(output_path))

    console.print("✅ Embedding process complete.")
    console.print(f"Shape of the new DataFrame: {embedded_df.shape}")


if __name__ == "__main__":
    app()
