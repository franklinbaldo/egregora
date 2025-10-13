"""CLI entry point for the ingestion subsystem."""

from __future__ import annotations

from pathlib import Path

import typer

from .parser import parse_multiple
from .anonymizer import Anonymizer
from ..models import WhatsAppExport

app = typer.Typer()


import polars as pl

@app.command()
def ingest_zip(zip_path: Path) -> pl.DataFrame:
    """Ingest a WhatsApp ZIP file and output a Polars DataFrame."""
    export = WhatsAppExport(
        zip_path=zip_path,
        group_name="Unknown",
        group_slug="unknown",
        export_date=zip_path.stat().st_mtime,
        chat_file="_chat.txt",
        media_files=[],
    )
    df = parse_multiple([export])
    df = Anonymizer.anonymize_dataframe(df)
    return df


if __name__ == "__main__":
    app()
