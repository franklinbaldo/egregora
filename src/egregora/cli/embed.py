"""CLI for embedding generation."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import typer

from ..embed.embed import embed_dataframe, export_to_parquet
from ..config import PipelineConfig

app = typer.Typer()

@app.command()
def embed(
    input_path: Path = typer.Argument(..., help="Path to the input DataFrame file."),
    output_path: Path = typer.Argument(..., help="Path to the output Parquet file."),
) -> None:
    """Embeds the 'message' column of a DataFrame and saves it to a Parquet file."""
    config = PipelineConfig()
    df = pl.read_parquet(input_path)
    df = embed_dataframe(df, batch_size=config.embed.batch_size)
    export_to_parquet(df, str(output_path))
    print(f"Embedding complete. Output saved to {output_path}")

if __name__ == "__main__":
    app()
