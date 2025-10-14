"""CLI entry point for the archive subsystem."""

from __future__ import annotations

import typer
from rich.console import Console
from internetarchive import search_items, download, upload
from datetime import date
from pathlib import Path

console = Console()
app = typer.Typer(help="Manage the Internet Archive for embeddings.")


@app.command("download")
def download(
    identifier: str = typer.Option(
        "egregora-vectors", "--identifier", help="The Internet Archive identifier."
    ),
    version: str = typer.Option("latest", "--version", help="The version to download."),
) -> None:
    """Downloads embeddings from the Internet Archive."""
    console.print(f"📥 Downloading embeddings from Internet Archive...")
    console.print(f"   Identifier: {identifier}")
    console.print(f"   Version: {version}")

    query = f"identifier:{identifier}"
    if version != "latest":
        query += f" AND version:{version}"

    search = search_items(query)

    if not search:
        console.print(f"❌ No items found for identifier: {identifier}")
        raise typer.Exit(1)

    item = search[0]
    console.print(f"   Found item: {item.identifier}")
    download(item.identifier, verbose=True)
    console.print("✅ Download complete.")


@app.command("upload")
def upload_command(
    parquet_file: Path = typer.Argument(..., help="Path to the Parquet file to upload."),
    identifier: str = typer.Option(
        "egregora-vectors", "--identifier", help="The Internet Archive identifier."
    ),
) -> None:
    """Uploads a Parquet file to the Internet Archive."""
    console.print(f"🚀 Uploading {parquet_file} to Internet Archive...")
    console.print(f"   Identifier: {identifier}")

    if not parquet_file.exists():
        console.print(f"❌ File not found: {parquet_file}")
        raise typer.Exit(1)

    # The plan specifies using today's date in the identifier
    today = date.today().isoformat()
    item_identifier = f"{identifier}-{today}"

    with open(parquet_file, "rb") as f:
        upload(
            item_identifier,
            files={parquet_file.name: f},
            metadata={"title": f"Egregora Vectors {today}", "date": today},
        )
    console.print("✅ Upload complete.")


if __name__ == "__main__":
    app()
