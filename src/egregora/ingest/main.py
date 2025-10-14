"""CLI entry point for the ingest subsystem."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from ..models import WhatsAppExport
from ..parser import parse_export

console = Console()
app = typer.Typer(help="Ingest and parse WhatsApp ZIP files into a DataFrame.")


def _extract_group_name_from_chat_file(chat_filename: str) -> str:
    """Extract group name from WhatsApp chat filename."""
    base_name = chat_filename.replace(".txt", "")
    if "Conversa do WhatsApp com " in base_name:
        return base_name.replace("Conversa do WhatsApp com ", "").strip()
    if "WhatsApp Chat with " in base_name:
        return base_name.replace("WhatsApp Chat with ", "").strip()
    return base_name


def _generate_group_slug(group_name: str) -> str:
    """Generate a URL-friendly slug from group name."""
    return group_name.lower().replace(" ", "-").strip()


@app.command("run")
def ingest_zip(
    zip_path: Path = typer.Argument(..., help="Path to the WhatsApp ZIP file."),
    output_path: Path = typer.Option(
        None, "--output", "-o", help="Path to save the output Parquet file."
    ),
) -> None:
    """
    Ingests a WhatsApp ZIP file, parses it, and saves the resulting DataFrame.
    """
    console.print(f"📥 Ingesting ZIP file: {zip_path}")

    if not zip_path.exists():
        console.print(f"❌ File not found: {zip_path}")
        raise typer.Exit(1)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
            if not txt_files:
                console.print(f"❌ No .txt file found in {zip_path}")
                raise typer.Exit(1)
            chat_file = txt_files[0]
            media_files = [f for f in zf.namelist() if f != chat_file]
            group_name = _extract_group_name_from_chat_file(chat_file)
            group_slug = _generate_group_slug(group_name)

    except zipfile.BadZipFile:
        console.print(f"❌ Invalid ZIP file: {zip_path}")
        raise typer.Exit(1) from None

    export = WhatsAppExport(
        zip_path=zip_path,
        group_name=group_name,
        group_slug=group_slug,
        export_date=date.today(),
        chat_file=chat_file,
        media_files=media_files,
    )

    df = parse_export(export)

    if output_path:
        console.print(f"💾 Saving DataFrame to: {output_path}")
        df.write_parquet(output_path)

    console.print("✅ Ingestion complete.")
    console.print("DataFrame head:")
    console.print(df.head())
    console.print(f"Shape: {df.shape}")


if __name__ == "__main__":
    app()
