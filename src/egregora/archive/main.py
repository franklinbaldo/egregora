"""CLI entry point for the archive subsystem."""

from __future__ import annotations

import typer
from rich.console import Console
from internetarchive import search_items, download

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

    search = search_items(query, sort_by="publicdate desc")

    if not search:
        console.print(f"❌ No items found for identifier: {identifier}")
        raise typer.Exit(1)

    item = search[0]
    console.print(f"   Found item: {item.identifier}")
    download(item.identifier, verbose=True)
    console.print("✅ Download complete.")


if __name__ == "__main__":
    app()
